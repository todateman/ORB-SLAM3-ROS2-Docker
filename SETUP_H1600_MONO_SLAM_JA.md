# H1600 Cam 単眼SLAM セットアップ手順

## 1. 概要

Venus USB2.0 Camera H1600 Cam（`0ac8:3420`）を使って、Docker コンテナ内で ORB-SLAM3 の単眼SLAMを動作させる手順です。  
H1600 は v4l2_camera で MJPG が非対応のため、OpenCV + Python スクリプトでカメラ映像を配信します。

---

## 2. H1600 セットアップ手順

### 2.1. X11 ソケットのマウント追加

コンテナ再起動後に GUI が表示されるよう `docker-compose.yml` の `orb_slam3_22_humble_nvidia` サービスに以下を追加済みです。

```yaml
volumes:
  - /tmp/.X11-unix:/tmp/.X11-unix:rw
```

また、ホスト側で X11 アクセスを許可します。

```bash
xhost +local:docker
```

### 2.2. カメラパッケージのインストール

コンテナ再起動後は毎回インストールが必要です（イメージには含まれていません）。

```bash
docker exec <CONTAINER_ID> bash -c "
  apt-get update -qq && \
  apt-get install -y ros-humble-camera-calibration
"
```

### 2.3. カメラキャリブレーション

H1600 は MJPG フォーマットのみ対応（H264 は v4l2_camera 非対応）。  
`usb_cam` を使って 1280x720 MJPG で配信し、`camera_calibration` でキャリブレーションします。

```bash
# パッケージインストール（初回のみ）
docker exec <CONTAINER_ID> bash -c "apt-get install -y ros-humble-usb-cam"

# ターミナル1: usb_cam ノード起動（MJPG フォーマット指定）
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  ros2 run usb_cam usb_cam_node_exe --ros-args \
    -p video_device:=/dev/video0 \
    -p image_width:=1280 \
    -p image_height:=720 \
    -p pixel_format:=mjpeg2rgb \
    -p camera_frame_id:=camera \
    -p framerate:=30.0
"

# ターミナル2: キャリブレーションツール起動
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  ros2 run camera_calibration cameracalibrator \
    --size 8x6 --square 0.025 \
    --ros-args -r image:=/image_raw -r camera:=/camera
"
```

> **注意**: GUI が表示されたらチェッカーボード（[media/Checkerboard-A4-25mm-8x6.pdf](media/Checkerboard-A4-25mm-8x6.pdf)）を様々な角度・距離で映し、X/Y/Size/Skew バーが全て緑になったら **CALIBRATE** ボタンを押します。計算中は「応答がありません」と表示されますが、**Ctrl+C を押さずに待ちます**。

キャリブレーション完了後、ターミナルに表示される値を記録します。

```
D = [k1, k2, p1, p2, ...]
K = [fx, 0, cx, 0, fy, cy, 0, 0, 1]
```

### 2.4. ORB-SLAM3 キャリブレーションファイルの作成

配信解像度は **640x360**（1280x720 の 0.5 倍）のため、fx/fy/cx/cy もすべて 0.5 倍にスケーリングします。

```bash
docker exec <CONTAINER_ID> bash -c "printf '%s\n' \
'%YAML:1.0' \
'' \
'File.version: \"1.0\"' \
'' \
'Camera.type: \"PinHole\"' \
'' \
'Camera1.fx: 335.390069' \
'Camera1.fy: 335.827256' \
'Camera1.cx: 341.483448' \
'Camera1.cy: 183.854404' \
'' \
'Camera1.k1: -0.342989' \
'Camera1.k2: 0.091277' \
'Camera1.p1: -0.000018' \
'Camera1.p2: -0.003789' \
'' \
'Camera.width: 640' \
'Camera.height: 360' \
'Camera.fps: 30' \
'Camera.RGB: 1' \
'' \
'ORBextractor.nFeatures: 1000' \
'ORBextractor.scaleFactor: 1.2' \
'ORBextractor.nLevels: 8' \
'ORBextractor.iniThFAST: 20' \
'ORBextractor.minThFAST: 7' \
'' \
'Viewer.KeyFrameSize: 0.05' \
'Viewer.KeyFrameLineWidth: 1.0' \
'Viewer.GraphLineWidth: 0.9' \
'Viewer.PointSize: 2.0' \
'Viewer.CameraSize: 0.08' \
'Viewer.CameraLineWidth: 3.0' \
'Viewer.ViewpointX: 0.0' \
'Viewer.ViewpointY: -0.7' \
'Viewer.ViewpointZ: -1.8' \
'Viewer.ViewpointF: 500.0' \
> /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/orb_slam3_params/h1600_mono.yaml"
```

> fx, fy, cx, cy, k1, k2, p1, p2 の値は実際のキャリブレーション結果を 0.5 倍にして置き換えてください。

BOM 確認:

```bash
docker exec <CONTAINER_ID> bash -c "
  xxd /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/orb_slam3_params/h1600_mono.yaml | head -1
"
# 先頭が "25 59 41 4d" (=%YAML) であること
```

### 2.5. ROS2 パラメータファイルの作成

**ファイルパス**: `orb_slam3_ros2_wrapper/params/ros_params/h1600-mono-ros-params.yaml`

```yaml
# H1600 Cam 単眼カメラ用 ROSパラメータ
ORB_SLAM3_MONO_ROS2:
  ros__parameters:
    robot_base_frame: base_footprint
    global_frame: map
    odom_frame: odom
    image_topic_name: /image_raw
    robot_x: 0.0
    robot_y: 0.0
    robot_z: 0.0
    robot_qx: 0.0
    robot_qy: 0.0
    robot_qz: 0.0
    robot_qw: 1.0
    visualization: true
    odometry_mode: false
    publish_tf: true
    map_data_publish_frequency: 1000
    do_loop_closing: false
```

### 2.6. シンボリックリンクの作成

```bash
docker exec <CONTAINER_ID> bash -c "
  ln -sf /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/orb_slam3_params/h1600_mono.yaml \
    /root/colcon_ws/install/orb_slam3_ros2_wrapper/share/orb_slam3_ros2_wrapper/params/orb_slam3_params/h1600_mono.yaml && \
  ln -sf /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/ros_params/h1600-mono-ros-params.yaml \
    /root/colcon_ws/install/orb_slam3_ros2_wrapper/share/orb_slam3_ros2_wrapper/params/ros_params/h1600-mono-ros-params.yaml
"
```

---

## 3. H1600 SLAM 実行方法

### 3.1. カメラノードの起動（Python スクリプト）

H1600 は v4l2_camera・usb_cam ともに MJPG の安定配信に問題があるため、OpenCV + Python スクリプトを使用します。  
`/root/camera_pub.py` をコンテナ内に配置します（`docker cp` またはボリュームマウント経由）。

**スクリプト内容** (`camera_pub.py`):

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraPublisher(Node):
    def __init__(self):
        super().__init__('camera_publisher')
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.pub = self.create_publisher(Image, '/image_raw', qos)
        self.bridge = CvBridge()

        self.cap = cv2.VideoCapture('/dev/video0', cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        self.get_logger().info('カメラ起動: 1280x720 → 640x360 MJPG @ 30fps')

    def run(self):
        while rclpy.ok():
            ret, frame = self.cap.read()
            if not ret:
                continue
            frame = cv2.resize(frame, (640, 360))
            msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'camera'
            self.pub.publish(msg)

    def destroy_node(self):
        self.cap.release()
        super().destroy_node()

def main():
    rclpy.init()
    node = CameraPublisher()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
```

起動コマンド:

```bash
docker exec -d <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  python3 /root/camera_pub.py > /tmp/camera_pub.log 2>&1"
```

### 3.2. ORB-SLAM3 の起動

```bash
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  source /root/colcon_ws/install/setup.bash && \
  ros2 launch orb_slam3_ros2_wrapper unirobot.launch.py \
    sensor_config:=mono \
    orb_slam3_param_file:=h1600_mono.yaml \
    ros_params_file:=h1600-mono-ros-params.yaml
"
```

---

## 4. 録画動画から SLAM を実行する

### 4.1. 概要

H1600 で撮影した動画ファイル（MP4）を `/image_raw` トピックに配信して SLAM を実行できます。

### 4.2. 動画配信スクリプト

以下のスクリプト (`video_pub.py`) をコンテナに配置します。

```python
#!/usr/bin/env python3
"""
H1600カメラで撮影した動画をROS2のimage_rawトピックに配信するスクリプト。
1920x1080を640x360にリサイズして配信（h1600_mono.yaml のキャリブレーションに合わせる）。
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import time
import sys

VIDEO_PATH = '/root/20250928_133344.MP4'  # 動画ファイルパスを変更してください
OUTPUT_W = 640
OUTPUT_H = 360
TARGET_FPS = 30.0

class VideoPublisher(Node):
    def __init__(self):
        super().__init__('video_publisher')
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.pub = self.create_publisher(Image, '/image_raw', qos)
        self.bridge = CvBridge()
        self.cap = cv2.VideoCapture(VIDEO_PATH)
        if not self.cap.isOpened():
            self.get_logger().error(f'動画を開けません: {VIDEO_PATH}')
            sys.exit(1)
        total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.get_logger().info(
            f'動画: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x'
            f'{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {fps}fps, '
            f'{total}フレーム ({total/fps:.1f}秒)'
        )

    def run(self):
        interval = 1.0 / TARGET_FPS
        frame_num = 0
        while rclpy.ok():
            t0 = time.time()
            ret, frame = self.cap.read()
            if not ret:
                self.get_logger().info('動画の末尾に達しました')
                break
            frame = cv2.resize(frame, (OUTPUT_W, OUTPUT_H))
            msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'camera'
            self.pub.publish(msg)
            frame_num += 1
            if frame_num % 150 == 0:
                self.get_logger().info(f'配信中: {frame_num}フレーム')
            elapsed = time.time() - t0
            if interval - elapsed > 0:
                time.sleep(interval - elapsed)

    def destroy_node(self):
        self.cap.release()
        super().destroy_node()

def main():
    rclpy.init()
    node = VideoPublisher()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
```

### 4.3. 実行手順

```bash
# ステップ1: 動画ファイルをコンテナにコピー
docker cp /path/to/your_video.MP4 <CONTAINER_ID>:/root/your_video.MP4

# ステップ2: video_pub.py をコンテナにコピー
docker cp /path/to/video_pub.py <CONTAINER_ID>:/root/video_pub.py

# ターミナル1: 動画配信ノード起動
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  python3 /root/video_pub.py"

# ターミナル2: ORB-SLAM3 起動
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  source /root/colcon_ws/install/setup.bash && \
  ros2 launch orb_slam3_ros2_wrapper unirobot.launch.py \
    sensor_config:=mono \
    orb_slam3_param_file:=h1600_mono.yaml \
    ros_params_file:=h1600-mono-ros-params.yaml"
```

---

## 5. H1600 トラブルシューティング

### 5.1. 映像が途切れがち（低FPS）

H1600 は v4l2_camera / usb_cam で MJPG が正しくデコードされず、`No JPEG data found in image` エラーが発生します。`camera_pub.py`（OpenCV直接読み取り）を使用してください。

| 構成 | 実測FPS |
| ---- | ------- |
| v4l2_camera（MJPG）| クラッシュ |
| usb_cam（mjpeg2rgb）| 約10fps（間欠ギャップあり） |
| **OpenCV + Python（1280x720）** | **約15fps** |
| **OpenCV + Python（640x360リサイズ）** | **約25fps** ✅ |

### 5.2. キャリブレーション中に GUI がフリーズする

CALIBRATEボタン押下後、多数のサンプル（100枚以上）では数分かかります。「応答がありません」のダイアログは**「待つ」を選択**してください。Ctrl+Cで中断すると再度サンプル収集からやり直しになります。

### 5.3. usb_cam が H264 モードで起動してしまう

```bash
# v4l2-ctl で明示的に MJPG に切り替えてから usb_cam を起動する
docker exec <CONTAINER_ID> bash -c "
  v4l2-ctl --device=/dev/video0 \
    --set-fmt-video=width=1280,height=720,pixelformat=MJPG"
```

---

## 6. H1600 関連ファイル

| ファイル | 用途 |
| -------- | ---- |
| `orb_slam3_ros2_wrapper/params/orb_slam3_params/h1600_mono.yaml` | H1600キャリブレーション・ORB設定（640x360） |
| `orb_slam3_ros2_wrapper/params/ros_params/h1600-mono-ros-params.yaml` | ROS2トピック・フレーム設定 |
| `container_root/` 内 `camera_pub.py` | OpenCV MJPG カメラ配信スクリプト |
| `container_root/` 内 `video_pub.py` | 録画動画配信スクリプト |
