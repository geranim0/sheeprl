import copy
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Sequence, SupportsFloat, Tuple, Union

import gymnasium as gym
import numpy as np
from gymnasium.core import Env, RenderFrame

import gymnasium.spaces as spaces
import melee_env.env_v2

class MaskVelocityWrapper(gym.ObservationWrapper):
    """
    Gym environment observation wrapper used to mask velocity terms in
    observations. The intention is the make the MDP partially observable.
    Adapted from https://github.com/LiuWenlin595/FinalProject.
    """

    # Supported envs
    velocity_indices = {
        "CartPole-v0": np.array([1, 3]),
        "CartPole-v1": np.array([1, 3]),
        "MountainCar-v0": np.array([1]),
        "MountainCarContinuous-v0": np.array([1]),
        "Pendulum-v1": np.array([2]),
        "LunarLander-v2": np.array([2, 3, 5]),
        "LunarLanderContinuous-v2": np.array([2, 3, 5]),
    }

    def __init__(self, env: gym.Env):
        super().__init__(env)

        assert env.unwrapped.spec is not None
        env_id: str = env.unwrapped.spec.id
        # By default no masking
        self.mask = np.ones_like(env.observation_space.sample())
        try:
            # Mask velocity
            self.mask[self.velocity_indices[env_id]] = 0.0
        except KeyError as e:
            raise NotImplementedError(f"Velocity masking not implemented for {env_id}") from e

    def observation(self, observation: np.ndarray) -> np.ndarray:
        return observation * self.mask


class ActionRepeat(gym.Wrapper):
    def __init__(self, env: gym.Env, amount: int = 1):
        super().__init__(env)
        if amount <= 0:
            raise ValueError("`amount` should be a positive integer")
        self._amount = amount

    @property
    def action_repeat(self) -> int:
        return self._amount

    def __getattr__(self, name):
        return getattr(self.env, name)

    def step(self, action):
        done = False
        truncated = False
        current_step = 0
        total_reward = 0.0
        while current_step < self._amount and not (done or truncated):
            obs, reward, done, truncated, info = self.env.step(action)
            total_reward += reward
            current_step += 1
        return obs, total_reward, done, truncated, info

class RingBuffer:
    def __init__(self, capacity):
        self.capacity = capacity
        self.data = [None] * capacity
        self.size = 0
        self.start = 0

    def __len__(self):
        return self.size

    def append(self, item):
        if self.size < self.capacity:
            self.data[(self.start + self.size) % self.capacity] = item
            self.size += 1
        else:
            self.data[self.start] = item
            self.start = (self.start + 1) % self.capacity

    def get(self, index):
        if index < 0 or index >= self.size:
            raise IndexError("Index out of range")
        return self.data[(self.start + index) % self.capacity]

class InputBuffer_Atari(gym.Wrapper):
    def __init__(self, env: gym.Env, input_buffer_amount: int = 0):
        super().__init__(env)
        if input_buffer_amount <= 0:
            raise ValueError("`amount` should be a positive integer")
        self._input_buffer_amount = input_buffer_amount
        self._input_buf = RingBuffer(input_buffer_amount)

    @property
    def input_buf_len(self) -> int:
        return self._input_buffer_amount
    
    def __getattr__(self, name):
        return getattr(self.env, name)
    
    def step(self, action):
        if self._input_buf.size == self._input_buf.capacity:
            this_frame_action = self._input_buf.get(0)
        else:
            this_frame_action = self.env.action_space.sample()

        
        #print('current action = ' + str(action))
        #print('this_frame_action action = ' + str(this_frame_action))
        self._input_buf.append(action)
        
        return self.env.step(this_frame_action)

# like InputBuffer but we feed input buffer as observation
class InputBufferWtihActionsAsInput_Atari(gym.Wrapper):
    def __init__(self, env: gym.Env, input_buffer_amount: int = 0):
        super().__init__(env)
        if input_buffer_amount <= 0:
            raise ValueError("`amount` should be a positive integer")
        self._input_buffer_amount = input_buffer_amount
        self._input_buf = deque(maxlen=input_buffer_amount)
        self.observation_space = gym.spaces.Dict({
                "rgb": self.env.observation_space,
                #"last_action": self.env.action_space
                #"actions": gym.spaces.Box(shape=(self.env.action_space.shape, input_buffer_amount), dtype=np.int64)
                #"actions": gym.spaces.Box([self.env.action_space] * input_buffer_amount)
                "actions": gym.spaces.Tuple([self.env.action_space] * input_buffer_amount)
            })
        

    #@property
    #def input_buf_len(self) -> int:
    #    return self._input_buffer_amount
    
    #def __getattr__(self, name):
    #    return getattr(self.env, name)

    def reset(self, **kwargs):
        obs, infos = super().reset(**kwargs)
        
        while len(self._input_buf) < self._input_buf.maxlen:
            self._input_buf.append(self.env.action_space.sample())
        
        return self.get_obs(obs), infos
    
    def get_obs(self, observation: Any) -> Any:
        #observation['past_actions'] = spaces.Space(list(self._input_buf))
        return {
            "rgb": observation,
            #"last_action": self._input_buf[0]
            #"actions": np.array(self._input_buf, dtype=np.int64)
            "actions": self._input_buf
        }
        #return observation
        #return spaces.Dict({
            #"rgb": observation,})
            #"past_actions": self._input_buf})

    def step(self, action):        
        this_frame_action = self._input_buf[0]

        #print('current action = ' + str(action))
        #print('this_frame_action action = ' + str(this_frame_action))
        self._input_buf.append(action)
        
        obs, reward, done, truncated, infos = self.env.step(this_frame_action)

        #obs = self._get_obs(obs)

        return self.get_obs(obs), reward, done, truncated, infos


class InputBufferWtihActionsAsInput_Atari_v2(gym.Wrapper):
    def __init__(self, env: gym.Env, input_buffer_amount: int = 0):
        super().__init__(env)
        if input_buffer_amount <= 0:
            raise ValueError("`amount` should be a positive integer")
        self._input_buffer_amount = input_buffer_amount
        self._input_buf = deque(maxlen=input_buffer_amount)
        self.observation_space = gym.spaces.Dict({
                "rgb": self.env.observation_space,
                #"last_action": self.env.action_space
                #"actions": gym.spaces.Box(shape=(self.env.action_space.shape, input_buffer_amount), dtype=np.int64)
                #"actions": gym.spaces.Box([self.env.action_space] * input_buffer_amount)
                "actions_0": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_1": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_2": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_3": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_4": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_5": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_6": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_7": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_8": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_9": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_10": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
                "actions_11": gym.spaces.Box(low=0, high=8, shape=(1,), dtype=np.int8),
            })
        

    #@property
    #def input_buf_len(self) -> int:
    #    return self._input_buffer_amount
    
    #def __getattr__(self, name):
    #    return getattr(self.env, name)

    def reset(self, **kwargs):
        obs, infos = super().reset(**kwargs)
        
        while len(self._input_buf) < self._input_buf.maxlen:
            self._input_buf.append(self.env.action_space.sample())
        
        return self.get_obs(obs), infos
    
    def get_obs(self, observation: Any) -> Any:
        #observation['past_actions'] = spaces.Space(list(self._input_buf))
        return {
            "rgb": observation,
            #"last_action": self._input_buf[0]
            #"actions": np.array(self._input_buf, dtype=np.int64)
            "actions_0": self._input_buf[0],
            "actions_1": self._input_buf[1],
            "actions_2": self._input_buf[2],
            "actions_3": self._input_buf[3],
            "actions_4": self._input_buf[4],
            "actions_5": self._input_buf[5],
            "actions_6": self._input_buf[6],
            "actions_7": self._input_buf[7],
            "actions_8": self._input_buf[8],
            "actions_9": self._input_buf[9],
            "actions_10": self._input_buf[10],
            "actions_11": self._input_buf[11],
        }
        #return observation
        #return spaces.Dict({
            #"rgb": observation,})
            #"past_actions": self._input_buf})

    def step(self, action):        
        this_frame_action = self._input_buf[0]

        #print('current action = ' + str(action))
        #print('this_frame_action action = ' + str(this_frame_action))
        self._input_buf.append(action)
        
        obs, reward, done, truncated, infos = self.env.step(this_frame_action)

        #obs = self._get_obs(obs)

        return self.get_obs(obs), reward, done, truncated, infos

class RestartOnException(gym.Wrapper):
    def __init__(self, env_fn: Callable[..., gym.Env], exceptions=(Exception,), window=300, maxfails=2, wait=20):
        if not isinstance(exceptions, (tuple, list)):
            exceptions = [exceptions]
        self._env_fn = env_fn
        self._exceptions = tuple(exceptions)
        self._window = window
        self._maxfails = maxfails
        self._wait = wait
        self._last = time.time()
        self._fails = 0
        super().__init__(self._env_fn())

    def step(self, action) -> Tuple[Any, SupportsFloat, bool, bool, Dict[str, Any]]:
        try:
            return self.env.step(action)
        except self._exceptions as e:
            if time.time() > self._last + self._window:
                self._last = time.time()
                self._fails = 1
            else:
                self._fails += 1
            if self._fails > self._maxfails:
                raise RuntimeError(f"The env crashed too many times: {self._fails}")
            gym.logger.warn(f"STEP - Restarting env after crash with {type(e).__name__}: {e}")
            time.sleep(self._wait)
            self.env = self._env_fn()
            new_obs, info = self.env.reset()
            info.update({"restart_on_exception": True})
            return new_obs, 0.0, False, False, info

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[Any, Dict[str, Any]]:
        try:
            return self.env.reset(seed=seed, options=options)
        except self._exceptions as e:
            if time.time() > self._last + self._window:
                self._last = time.time()
                self._fails = 1
            else:
                self._fails += 1
            if self._fails > self._maxfails:
                raise RuntimeError(f"The env crashed too many times: {self._fails}")
            gym.logger.warn(f"RESET - Restarting env after crash with {type(e).__name__}: {e}")
            time.sleep(self._wait)
            self.env = self._env_fn()
            new_obs, info = self.env.reset(seed=seed, options=options)
            info.update({"restart_on_exception": True})
            return new_obs, info


class FrameStack(gym.Wrapper):
    def __init__(self, env: Env, num_stack: int, cnn_keys: Sequence[str], dilation: int = 1) -> None:
        super().__init__(env)
        if num_stack <= 0:
            raise ValueError(f"Invalid value for num_stack, expected a value greater than zero, got {num_stack}")
        if not isinstance(env.observation_space, gym.spaces.Dict):
            raise RuntimeError(
                f"Expected an observation space of type gym.spaces.Dict, got: {type(env.observation_space)}"
            )
        self._num_stack = num_stack
        self._cnn_keys = []
        self._dilation = dilation
        self.observation_space = copy.deepcopy(self.env.observation_space)
        for k, v in self.env.observation_space.spaces.items():
            if cnn_keys and len(v.shape) == 3:
                self._cnn_keys.append(k)
                self.observation_space[k] = gym.spaces.Box(
                    np.repeat(self.env.observation_space[k].low[None, ...], num_stack, axis=0),
                    np.repeat(self.env.observation_space[k].high[None, ...], num_stack, axis=0),
                    (self._num_stack, *self.env.observation_space[k].shape),
                    self.env.observation_space[k].dtype,
                )

        if self._cnn_keys is None or len(self._cnn_keys) == 0:
            raise RuntimeError("Specify at least one valid cnn key to be stacked")
        self._frames = {k: deque(maxlen=num_stack * dilation) for k in self._cnn_keys}

    def _get_obs(self, key):
        frames_subset = list(self._frames[key])[self._dilation - 1 :: self._dilation]
        assert len(frames_subset) == self._num_stack
        return np.stack(list(frames_subset), axis=0)

    def step(self, action: Any) -> Tuple[Any, SupportsFloat, bool, bool, Dict[str, Any]]:
        obs, reward, done, truncated, infos = self.env.step(action)
        for k in self._cnn_keys:
            self._frames[k].append(obs[k])
            if (
                "env_domain" in infos
                and infos["env_domain"] == "DIAMBRA"
                and len(set(["round_done", "stage_done", "game_done"]).intersection(infos.keys())) == 3
                and (infos["round_done"] or infos["stage_done"] or infos["game_done"])
                and not (done or truncated)
            ):
                for _ in range(self._num_stack * self._dilation - 1):
                    self._frames[k].append(obs[k])
            obs[k] = self._get_obs(k)
        return obs, reward, done, truncated, infos

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Tuple[Any, Dict[str, Any]]:
        obs, infos = self.env.reset(seed=seed, **kwargs)
        [self._frames[k].clear() for k in self._cnn_keys]
        for k in self._cnn_keys:
            [self._frames[k].append(obs[k]) for _ in range(self._num_stack * self._dilation)]
            obs[k] = self._get_obs(k)
        return obs, infos


class RewardAsObservationWrapper(gym.Wrapper):
    """It adds the reward to the observations.
    The reward is assumed to be a float scalar, so the reward converted as observation is a gymnasium.spaces.Box
    with shape (1,). Moreover, it tries to get the reward range from the environment to wrap, otherwise it assumes
    that the reward has no range (-inf, +inf).

    It converts the observation space (if it is not already) in gymnasium.spaces.Dict. In case the observation
    space of the environment is a dictionary, then it simply adds the `reward` key in the dictionary, otherwise,
    it creates a dictionary with two keys:
    1. `obs`: the observations of the environment.
    2. `reward`: the reward obtained by the agent.

    Args:
        env (Env): the environment to wrap.
    """

    def __init__(self, env: Env) -> None:
        super().__init__(env)
        reward_range = (
            self.env.reward_range or (-np.inf, np.inf) if hasattr(self.env, "reward_range") else (-np.inf, np.inf)
        )
        # The reward is assumed to be a scalar
        if isinstance(self.env.observation_space, gym.spaces.Dict):
            self.observation_space = gym.spaces.Dict(
                {
                    "reward": gym.spaces.Box(*reward_range, (1,), np.float32),
                    **{k: v for k, v in self.env.observation_space.items()},
                }
            )
        else:
            self.observation_space = gym.spaces.Dict(
                {"obs": self.env.observation_space, "reward": gym.spaces.Box(*reward_range, (1,), np.float32)}
            )

    def __getattr__(self, name):
        return getattr(self.env, name)

    def _convert_obs(self, obs: Any, reward: Union[float, np.ndarray]) -> Dict[str, Any]:
        reward_obs = (np.array(reward) if not isinstance(reward, np.ndarray) else reward).reshape(-1)
        if isinstance(obs, dict):
            obs["reward"] = reward_obs
        else:
            obs = {
                "obs": obs,
                "reward": reward_obs,
            }
        return obs

    def step(self, action: Any) -> Tuple[Any, SupportsFloat, bool, bool, Dict[str, Any]]:
        obs, reward, done, truncated, infos = self.env.step(action)
        return self._convert_obs(obs, copy.deepcopy(reward)), reward, done, truncated, infos

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[Any, Dict[str, Any]]:
        obs, infos = self.env.reset(seed=seed, options=options)
        return self._convert_obs(obs, 0), infos


class GrayscaleRenderWrapper(gym.Wrapper):
    def __init__(self, env: Env):
        super().__init__(env)

    def render(self) -> Optional[Union[RenderFrame, List[RenderFrame]]]:
        frame = super().render()
        if isinstance(frame, np.ndarray):
            if len(frame.shape) == 2:
                frame = frame[..., np.newaxis]
            if len(frame.shape) == 3 and frame.shape[-1] == 1:
                frame = frame.repeat(3, axis=-1)
        return frame


class ActionsAsObservationWrapper(gym.Wrapper):
    def __init__(self, env: Env, num_stack: int, dilation: int = 1):
        super().__init__(env)
        self._num_stack = num_stack
        self._dilation = dilation
        self._actions = deque(maxlen=num_stack * dilation)
        self._is_continuous = isinstance(self.env.action_space, gym.spaces.Box)
        self._is_multidiscrete = isinstance(self.env.action_space, gym.spaces.MultiDiscrete)
        self.observation_space = copy.deepcopy(self.env.observation_space)
        if self._is_continuous:
            self._action_shape = self.action_space.shape[0]
            low = np.resize(self.action_space.low, self._action_shape * num_stack)
            high = np.resize(self.action_space.high, self._action_shape * num_stack)
        elif self._is_multidiscrete:
            low = 0
            high = max(self.action_space.nvec)
            self._action_shape = len(self.env.action_space.shape)
        else:
            low = 0
            high = 1
            self._action_shape = self.action_space.n
        self.observation_space["action_stack"] = gym.spaces.Box(
            low=low, high=high, shape=(self._action_shape * num_stack,), dtype=np.float32
        )

    def step(self, action: Any) -> Tuple[Any | SupportsFloat | bool | Dict[str, Any]]:
        this_frame_action = self._actions[0]
        self._actions.append(action)
        obs, reward, done, truncated, info = super().step(this_frame_action)
        obs["action_stack"] = self._get_actions_stack()
        #print('this frame action ' + str(this_frame_action))
        #print('action buf = ' + str(self._actions))
        return obs, reward, done, truncated, info

    def reset(self, *, seed: int | None = None, options: Dict[str, Any] | None = None) -> Tuple[Any | Dict[str, Any]]:
        obs, info = super().reset(seed=seed, options=options)
        self._actions.clear()
        if self._is_multidiscrete or self._is_continuous:
            [self._actions.append(np.zeros((self._action_shape,))) for _ in range(self._num_stack * self._dilation)]
        else:
            [self._actions.append(0) for _ in range(self._num_stack * self._dilation)]
        obs["action_stack"] = self._get_actions_stack()
        return obs, info

    def _get_actions_stack(self) -> np.ndarray:
        actions_stack = list(self._actions)[self._dilation - 1 :: self._dilation]
        if self._is_continuous:
            actions = np.concatenate(actions_stack, axis=0)
        elif self._is_multidiscrete:
            actions = np.concatenate(actions_stack, axis=0)
        else:
            action_list = []
            for action in actions_stack:
                one_hot_action = np.zeros(self.action_space.n)
                one_hot_action[action] = 1
                action_list.append(one_hot_action)
            actions = np.concatenate(action_list, axis=0)
        #print(actions)
        return actions.astype(np.float32)
    


class ActionsAsObservationWrapper_multidiscrete_melee_v2(gym.Wrapper):
    def __init__(self, env: Env, num_stack: int, dilation: int = 1):
        print('using input buffer')
        super().__init__(env)
        self._num_stack = num_stack
        self._dilation = dilation
        self._actions = deque(maxlen=num_stack * dilation)
        self.observation_space = copy.deepcopy(self.env.observation_space)

        self.observation_space["action_stack"] = copy.deepcopy(self.env.action_space)

    def fill_input_buf(self):
        [self._actions.append(np.zeros()) for _ in range(self._num_stack)]

    def step(self, action: Any) -> Tuple[Any | SupportsFloat | bool | Dict[str, Any]]:
        this_frame_action = self._actions[0]
        self._actions.append(action)
        obs, reward, done, truncated, info = super().step(this_frame_action)
        obs["action_stack"] = self._get_actions_stack()
        #print('this frame action ' + str(this_frame_action))
        #print('action buf = ' + str(self._actions))
        return obs, reward, done, truncated, info

    def reset(self, *, seed: int | None = None, options: Dict[str, Any] | None = None) -> Tuple[Any | Dict[str, Any]]:
        obs, info = super().reset(seed=seed, options=options)
        obs["action_stack"] = self._get_actions_stack()
        return obs, info

    def _get_actions_stack(self) -> np.ndarray:
        if len(self._actions) < self.num_stack:
            self.fill_input_buf()

        actions_stack = list(self._actions)
        actions = np.concatenate(actions_stack, axis=0)
        return actions.astype(np.float32)