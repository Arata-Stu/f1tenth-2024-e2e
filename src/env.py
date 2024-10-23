import numpy as np
import math
import gym
from pyglet.gl import GL_POINTS

WAYPOINT_RADIUS = 0.5


class F110_Wrapped(gym.Wrapper):

    def __init__(self, env, map_manager, num_agent=1):
        super().__init__(env)

        self.state_n = self.env.num_beams
        self.action_n= 2

        self.num_agent = num_agent
        
        # store allowed steering/speed/lidar ranges for normalisation
        self.s_min = self.env.params['s_min']
        self.s_max = self.env.params['s_max']
        self.v_min = self.env.params['v_min']
        self.v_max = self.env.params['v_max']
        self.lidar_min = 0
        self.lidar_max = 30  # see ScanSimulator2D max_range

        # store car dimensions and some track info
        self.car_length = self.env.params['length']
        self.car_width = self.env.params['width']
        self.track_width = 3.2  # ~= track width, see random_trackgen.py

        # radius of circle where car can start on track, relative to a centerpoint
        self.start_radius = (self.track_width / 2) - \
            ((self.car_length + self.car_width) / 2)  # just extra wiggle room

        self.step_count = 0

        # set threshold for maximum angle of car, to prevent spinning
        self.max_theta = 100

        # self.waypoints = waypoints
        self.map_manager = map_manager
        # 描画されたWaypointを追跡するためのリスト
        self.drawn_waypoints = []
        self.current_target_index = 0  # 現在のターゲットWaypointのインデックス
        if self.map_manager.waypoints is not None:
            self.waypoints_passed = [False] * len(self.map_manager.waypoints)  # 各Waypointの通過状態を保持

        # Waypoint描画機能をレンダリングコールバックとして追加
        self.env.add_render_callback(self.render_waypoints)

        


    def step(self, action):
        
        observation, _, done, info = self.env.step(np.array(action))
        self.step_count += 1
        #spin
        if abs(observation['poses_theta'][0]) > self.max_theta:
            done = True
            
        #lap
        if observation['lap_counts'][0] == 2:
            done = True
            
        
        return observation, 0.0, done, info
    
    
    def reset(self, index=0):
        self.step_count = 0
        self.drawn_waypoints = []
        self.current_target_index = 10
        self.waypoints_passed = [False] * len(self.map_manager.waypoints) if self.map_manager.waypoints is not None else None

        positions = []

        if self.map_manager.waypoints is not None:
            num_waypoints = len(self.map_manager.waypoints)
            num_agents = self.num_agent

            # 各エージェントに対して均等にWaypointを割り当て
            index_increment = num_waypoints / num_agents

            for i in range(num_agents):
                # 浮動小数点のインデックスを整数インデックスに変換
                waypoint_index = int(i * index_increment + index) % num_waypoints 
                next_waypoint_index = (waypoint_index + 1) % num_waypoints

                x, y = self.map_manager.waypoints[waypoint_index][:2]
                next_x, next_y = self.map_manager.waypoints[next_waypoint_index][:2]
            
                # 角度を計算（ラジアン）
                dx = next_x - x
                dy = next_y - y
                t = math.atan2(dy, dx)

                positions.append([x, y, t])

        else:
            # Waypointsが存在しない場合のデフォルトの位置
            positions = [[0, 0, 0] for _ in range(self.num_agent)]

        observation, _, _, _ = self.env.reset(poses=np.array(positions))
        return observation
        
    def render_waypoints(self, renderer):
    
    # Waypointが設定されていない場合は何もしない
        if self.map_manager.waypoints is None:
            return
        
        # Waypoint座標の変換とスケーリング
        points = np.vstack((self.map_manager.waypoints[:, 0], self.map_manager.waypoints[:, 1])).T
        scaled_points = 50. * points  # スケーリング係数は状況に応じて調整
    
        # 各Waypointを描画
        for i in range(points.shape[0]):
            # 現在のターゲットWaypointは赤色で、それ以外は灰色で表示
            color = [255, 255, 255] if self.waypoints_passed[i] else [255,255,255]

            if len(self.drawn_waypoints) < points.shape[0]:
                b = renderer.batch.add(1, GL_POINTS, None,
                                   ('v3f/stream', [scaled_points[i, 0], scaled_points[i, 1], 0.]),
                                   ('c3B/stream', color))  # 色を設定
                self.drawn_waypoints.append(b)
            else:
                self.drawn_waypoints[i].vertices = [scaled_points[i, 0], scaled_points[i, 1], 0.]
                # 既存のWaypointの色を更新するには、描画オブジェクトに直接色を設定する必要があります。
                # 以下の行は、使用しているレンダリングシステムに応じて適切に調整する必要があります。
                self.drawn_waypoints[i].colors = color