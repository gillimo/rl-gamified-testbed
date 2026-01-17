"""Decomposed Policy Network - Multiple value heads for reward categories.

This module provides a custom policy for Stable-Baselines3 PPO that uses
separate value heads for different reward categories, enabling better
credit assignment when rewards come from multiple sources.

Reward Categories:
- exploration: New tiles, new buildings, HM usage
- battle: Damage dealt, knockouts, healing in battle
- progression: Level ups, badges, pokedex, money
- penalties: Menu penalties, fainted pokemon, stuck
- lava: Floor is Lava mode penalties
"""
import torch
import torch.nn as nn
from typing import Dict, List, Tuple, Type, Optional, Union
from gymnasium import spaces
import numpy as np

from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor, FlattenExtractor


# Reward categories matching reward_calculator.py
REWARD_CATEGORIES = ["exploration", "battle", "progression", "penalties", "lava"]


class DecomposedValueHead(nn.Module):
    """Multiple value heads - one per reward category.

    Each head predicts the expected value for its reward category,
    allowing the policy to learn separate value functions that
    combine to predict total expected return.
    """

    def __init__(self, feature_dim: int, categories: List[str] = None):
        """Initialize decomposed value head.

        Args:
            feature_dim: Dimension of input features from the shared network
            categories: List of reward category names
        """
        super().__init__()
        self.categories = categories or REWARD_CATEGORIES

        # One value head per category
        self.value_heads = nn.ModuleDict({
            cat: nn.Sequential(
                nn.Linear(feature_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 1)
            )
            for cat in self.categories
        })

        # Learnable weights for combining category values
        # Initialized to 1.0 so total value = sum of category values initially
        self.category_weights = nn.Parameter(torch.ones(len(self.categories)))

    def forward(self, features: torch.Tensor) -> Tuple[Dict[str, torch.Tensor], torch.Tensor]:
        """Compute value predictions for each category and total.

        Args:
            features: Tensor of shape (batch, feature_dim)

        Returns:
            category_values: Dict mapping category name to value tensor
            total_value: Combined value prediction
        """
        category_values = {}
        for cat in self.categories:
            category_values[cat] = self.value_heads[cat](features)

        # Total value = weighted sum of category values
        total = torch.zeros_like(category_values[self.categories[0]])
        for i, cat in enumerate(self.categories):
            weight = torch.softmax(self.category_weights, dim=0)[i]
            total = total + weight * category_values[cat]

        return category_values, total

    def get_category_value(self, features: torch.Tensor, category: str) -> torch.Tensor:
        """Get value prediction for a specific category."""
        return self.value_heads[category](features)


class DecomposedMlpExtractor(nn.Module):
    """Custom MLP feature extractor that outputs to decomposed value heads.

    This replaces the standard MlpExtractor to provide:
    1. Shared feature extraction layers
    2. Policy network head (for action distribution)
    3. Decomposed value heads (one per reward category)
    """

    def __init__(
        self,
        feature_dim: int,
        net_arch: List[int] = None,
        activation_fn: Type[nn.Module] = nn.ReLU,
        device: Union[torch.device, str] = "auto",
    ):
        """Initialize the decomposed MLP extractor.

        Args:
            feature_dim: Input feature dimension
            net_arch: List of hidden layer sizes
            activation_fn: Activation function class
            device: Torch device
        """
        super().__init__()

        if net_arch is None:
            net_arch = [256, 128]

        self.latent_dim_pi = net_arch[-1]
        self.latent_dim_vf = net_arch[-1]

        # Shared layers
        shared_layers = []
        last_dim = feature_dim
        for layer_size in net_arch[:-1]:
            shared_layers.append(nn.Linear(last_dim, layer_size))
            shared_layers.append(activation_fn())
            last_dim = layer_size

        self.shared_net = nn.Sequential(*shared_layers) if shared_layers else nn.Identity()

        # Policy network (separate head for action distribution)
        self.policy_net = nn.Sequential(
            nn.Linear(last_dim, net_arch[-1]),
            activation_fn(),
        )

        # Value network (feeds into decomposed heads)
        self.value_net = nn.Sequential(
            nn.Linear(last_dim, net_arch[-1]),
            activation_fn(),
        )

    def forward(self, features: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Extract features for policy and value networks.

        Args:
            features: Input features

        Returns:
            latent_pi: Features for policy network
            latent_vf: Features for value network
        """
        shared = self.shared_net(features)
        return self.policy_net(shared), self.value_net(shared)

    def forward_actor(self, features: torch.Tensor) -> torch.Tensor:
        """Extract features for actor (policy) only."""
        shared = self.shared_net(features)
        return self.policy_net(shared)

    def forward_critic(self, features: torch.Tensor) -> torch.Tensor:
        """Extract features for critic (value) only."""
        shared = self.shared_net(features)
        return self.value_net(shared)


class DecomposedActorCriticPolicy(ActorCriticPolicy):
    """Custom Actor-Critic policy with decomposed value heads.

    This policy maintains the standard PPO actor (policy) network while
    replacing the single value head with multiple category-specific heads.

    The total value is a learned weighted combination of category values,
    allowing the policy to:
    1. Learn separate value functions for different reward sources
    2. Better attribute credit when rewards compete
    3. Potentially learn category-specific baselines for variance reduction
    """

    def __init__(
        self,
        observation_space: spaces.Space,
        action_space: spaces.Space,
        lr_schedule,
        net_arch: Optional[List[int]] = None,
        activation_fn: Type[nn.Module] = nn.ReLU,
        *args,
        **kwargs,
    ):
        """Initialize the decomposed policy.

        Args:
            observation_space: Environment observation space
            action_space: Environment action space
            lr_schedule: Learning rate schedule
            net_arch: Network architecture (list of hidden layer sizes)
            activation_fn: Activation function
        """
        # Default architecture optimized for Pokemon Yellow
        if net_arch is None:
            net_arch = [256, 128]

        super().__init__(
            observation_space,
            action_space,
            lr_schedule,
            net_arch=net_arch,
            activation_fn=activation_fn,
            *args,
            **kwargs,
        )

        # Add decomposed value head after standard initialization
        self.decomposed_value_head = DecomposedValueHead(
            feature_dim=self.mlp_extractor.latent_dim_vf,
            categories=REWARD_CATEGORIES,
        )

    def forward(self, obs: torch.Tensor, deterministic: bool = False):
        """Forward pass through the policy.

        Args:
            obs: Observations
            deterministic: Whether to sample deterministically

        Returns:
            actions: Selected actions
            values: Total value predictions
            log_prob: Log probabilities of selected actions
        """
        # Get latent features
        features = self.extract_features(obs)
        if self.share_features_extractor:
            latent_pi, latent_vf = self.mlp_extractor(features)
        else:
            pi_features, vf_features = features
            latent_pi = self.mlp_extractor.forward_actor(pi_features)
            latent_vf = self.mlp_extractor.forward_critic(vf_features)

        # Get action distribution
        distribution = self._get_action_dist_from_latent(latent_pi)
        actions = distribution.get_actions(deterministic=deterministic)
        log_prob = distribution.log_prob(actions)

        # Get decomposed value (use total for standard PPO compatibility)
        _, total_value = self.decomposed_value_head(latent_vf)
        values = total_value.flatten()

        return actions, values, log_prob

    def predict_values(self, obs: torch.Tensor) -> torch.Tensor:
        """Predict values for given observations.

        Args:
            obs: Observations

        Returns:
            Total value predictions
        """
        features = self.extract_features(obs)
        if self.share_features_extractor:
            _, latent_vf = self.mlp_extractor(features)
        else:
            _, vf_features = features
            latent_vf = self.mlp_extractor.forward_critic(vf_features)

        _, total_value = self.decomposed_value_head(latent_vf)
        return total_value

    def get_decomposed_values(self, obs: torch.Tensor) -> Tuple[Dict[str, torch.Tensor], torch.Tensor]:
        """Get per-category and total value predictions.

        Args:
            obs: Observations

        Returns:
            category_values: Dict of category -> value tensor
            total_value: Combined value prediction
        """
        features = self.extract_features(obs)
        if self.share_features_extractor:
            _, latent_vf = self.mlp_extractor(features)
        else:
            _, vf_features = features
            latent_vf = self.mlp_extractor.forward_critic(vf_features)

        return self.decomposed_value_head(latent_vf)

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:
        """Evaluate actions for PPO loss computation.

        Args:
            obs: Observations
            actions: Actions to evaluate

        Returns:
            values: Value predictions
            log_prob: Log probabilities of actions
            entropy: Entropy of action distribution
        """
        features = self.extract_features(obs)
        if self.share_features_extractor:
            latent_pi, latent_vf = self.mlp_extractor(features)
        else:
            pi_features, vf_features = features
            latent_pi = self.mlp_extractor.forward_actor(pi_features)
            latent_vf = self.mlp_extractor.forward_critic(vf_features)

        distribution = self._get_action_dist_from_latent(latent_pi)
        log_prob = distribution.log_prob(actions)
        entropy = distribution.entropy()

        # Use total value for PPO
        _, total_value = self.decomposed_value_head(latent_vf)
        values = total_value.flatten()

        return values, log_prob, entropy
