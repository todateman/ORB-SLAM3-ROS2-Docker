# ORB-SLAM3 単眼SLAM セットアップ手順 (Logitech C270 + NVIDIA GPU + Docker)

## 概要

Logitech Webcam C270 を使って、Docker コンテナ内で ORB-SLAM3 の単眼SLAMを動作させる手順です。

## 前提条件

### ハードウェア

- NVIDIA GPU（本手順では RTX 5060 Ti で動作確認）
- Logitech Webcam C270（USB: `046d:0825`、`/dev/video0` として認識）
- Ubuntu ホスト OS

### ソフトウェア

| ソフトウェア | バージョン |
| ------------ | ---------- |
| NVIDIA ドライバ | 580.159.03 以上 |
| CUDA | 13.0 以上 |
| Docker | 最新版 |
| NVIDIA Container Toolkit | インストール済み |
| Docker Compose | v2 以上 |

### NVIDIA Container Toolkit の確認

```bash
# nvidia ランタイムが存在することを確認
docker info | grep -i runtime
# → "nvidia" が表示されること
```

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/suchetanrs/ORB-SLAM3-ROS2-Docker.git
cd ORB-SLAM3-ROS2-Docker
git submodule update --init --recursive --remote
```

### 2. X11 アクセス許可（ホスト側）

GUI ウィンドウ（ORB-SLAM3 ビューワー）を表示するために必要です。

```bash
xhost +local:docker
```

### 3. NVIDIA GPU 対応イメージのビルド

Dockerfile の `nvidia_gpu` ステージを使ってイメージをビルドします。

```bash
# リポジトリルートで実行
docker build \
  --target nvidia_gpu \
  -t orb-slam3-humble-nvidia:22.04 \
  .
```

> **注意**: ビルドには数分〜数十分かかります。OpenCV・Pangolin・Sophus などの依存関係がコンパイルされます。

ビルド完了の確認:

```bash
docker images | grep orb-slam3-humble-nvidia
# orb-slam3-humble-nvidia   22.04   <IMAGE_ID>   ...
```

### 4. NVIDIA GPU 対応コンテナの起動

```bash
docker compose up orb_slam3_22_humble_nvidia
```

別ターミナルでコンテナ ID を確認します。

```bash
docker ps
# CONTAINER ID を記録しておく（以降 <CONTAINER_ID> と記載）
```

### 4. ORB-SLAM3 本体のビルド（FastTrack）

コンテナ内で CUDA カーネルを含む ORB-SLAM3 をビルドします。

```bash
docker exec -it <CONTAINER_ID> bash -c "
  cd /home/orb/ORB_SLAM3 && \
  chmod +x build.sh && \
  ./build.sh
"
```

> **注意**: ビルドには数分〜数十分かかります。GPU CUDA カーネル（`fast.cu`, `descriptor.cu` 等）がコンパイルされます。

### 5. ROS2 ワークスペースのビルド（CUDA 有効）

```bash
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  cd /root/colcon_ws && \
  colcon build --symlink-install \
    --cmake-args -DORB_SLAM3_ROS2_WRAPPER_ENABLE_CUDA=ON
"
```

ビルド成功時の出力例:

```txt
Summary: 3 packages finished [...]
  orb_slam3_ros2_wrapper
  orb_slam3_map_generator
  slam_msgs
```

### 6. カメラドライバのインストール

```bash
docker exec -it <CONTAINER_ID> bash -c "
  apt-get update && \
  apt-get install -y ros-humble-v4l2-camera ros-humble-camera-calibration
"
```

### 7. カメラキャリブレーション

https://markhedleyjones.com/projects/calibration-checkerboard-collection からチェッカーボードを用意し、`camera_calibration` ツールでキャリブレーションを実施します。  

[media/Checkerboard-A4-25mm-8x6.pdf](media/Checkerboard-A4-25mm-8x6.pdf) は1マス25mm, 横8マス×縦6マス, A4サイズです。

```bash
# ターミナル1: カメラノード起動
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  ros2 run v4l2_camera v4l2_camera_node \
    --ros-args -p video_device:=/dev/video0 \
    -p image_size:=[640,480] \
    -p camera_frame_id:=camera
"

# ターミナル2: キャリブレーションツール起動
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  ros2 run camera_calibration cameracalibrator \
    --size 8x6 --square 0.025 \
    --ros-args -r image:=/image_raw
"
```

キャリブレーション完了後、取得したパラメータを記録します。

### 8. ORB-SLAM3 キャリブレーションファイルの作成

#### 8.1 BOMなしでYAMLファイルを作成

**重要**: VSCode などのエディタで作成すると UTF-8 BOM が付く場合があり、OpenCV YAMLパーサーが拒否します。コンテナ内で `printf` コマンドを使って作成してください。

```bash
docker exec <CONTAINER_ID> bash -c "printf '%s\n' \
'%YAML:1.0' \
'' \
'File.version: \"1.0\"' \
'' \
'Camera.type: \"PinHole\"' \
'' \
'Camera1.fx: 839.31585' \
'Camera1.fy: 837.67182' \
'Camera1.cx: 315.02911' \
'Camera1.cy: 234.81703' \
'' \
'Camera1.k1: 0.082510' \
'Camera1.k2: 0.122669' \
'Camera1.p1: -0.002734' \
'Camera1.p2: 0.000546' \
'' \
'Camera.width: 640' \
'Camera.height: 480' \
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
> /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/orb_slam3_params/c270_mono.yaml"
```

> fx, fy, cx, cy, k1, k2, p1, p2 の値はキャリブレーション結果で置き換えてください。

#### 8.2 BOMを確認

```bash
docker exec <CONTAINER_ID> bash -c "
  xxd /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/orb_slam3_params/c270_mono.yaml | head -1
"
# 先頭が "25 59 41 4d" (=%YAML) であること
# "ef bb bf" から始まる場合はBOMが残っているので再作成が必要
```

### 9. ROS2 パラメータファイルの作成

ホスト側（またはコンテナ内）でファイルを作成します。

**ファイルパス**: `orb_slam3_ros2_wrapper/params/ros_params/c270-mono-ros-params.yaml`

```yaml
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
    do_loop_closing: true
```

### 10. シンボリックリンクの作成

`--symlink-install` でビルドしても、ビルド後に追加したファイルは自動リンクされません。手動で作成します。

```bash
# ORB-SLAM3パラメータファイル
docker exec <CONTAINER_ID> bash -c "
  ln -sf /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/orb_slam3_params/c270_mono.yaml \
  /root/colcon_ws/install/orb_slam3_ros2_wrapper/share/orb_slam3_ros2_wrapper/params/orb_slam3_params/c270_mono.yaml
"

# ROSパラメータファイル
docker exec <CONTAINER_ID> bash -c "
  ln -sf /root/colcon_ws/src/orb_slam3_ros2_wrapper/params/ros_params/c270-mono-ros-params.yaml \
  /root/colcon_ws/install/orb_slam3_ros2_wrapper/share/orb_slam3_ros2_wrapper/params/ros_params/c270-mono-ros-params.yaml
"
```

---

## SLAM実行方法

### 1. カメラノードの起動

ホストPCに接続されたカメラ映像をROS2ノードでPublishします

```bash
docker exec -d <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  ros2 run v4l2_camera v4l2_camera_node \
    --ros-args \
    -p video_device:=/dev/video0 \
    -p image_size:=[640,480] \
    -p camera_frame_id:=camera \
    -p use_sensor_data_qos:=true
"
```

> `use_sensor_data_qos:=true` により、ORB-SLAM3 サブスクライバー（BEST_EFFORT）との QoS を合わせます。

### 2. ORB-SLAM3 の起動

カメラの特性に合わせたパラメータを読み込んでSLAMを実行します

```bash
docker exec -it <CONTAINER_ID> bash -c "
  source /opt/ros/humble/setup.bash && \
  source /root/colcon_ws/install/setup.bash && \
  ros2 launch orb_slam3_ros2_wrapper unirobot.launch.py \
    sensor_config:=mono \
    orb_slam3_param_file:=c270_mono.yaml \
    ros_params_file:=c270-mono-ros-params.yaml
"
```

---

## 動作確認

### 正常起動時のログ例

```txt
[mono-2] First KF:98; Map init KF:98
[mono-2] New Map created with 118 points
[mono-2] Current ORB-SLAM3 tracking frequency: 25.0022 frames / sec
```

### ビューワーの状態

| 表示 | 状態 |
| ---- | ---- |
| `WAITING FOR IMAGES` | 初期化待ち（画像受信中） |
| `TRYING TO INITIALIZE` | 特徴点マッチング中 |
| 点群表示 | 初期化成功・トラッキング中 |

### ORB-SLAM3 の Map Viewer（Pangolin GUI）のチェックボックス

| チェックボックス | 機能 |
| ---------------- | ---- |
| Follow Camera | 視点をカメラに追従させる。<BR>OFFにすると自由に視点を回転・移動できる |
| Show Points | 地図点（青い点群）の表示/非表示。<BR>マップ全体の3D構造を確認できる |
| Show KeyFrames | キーフレーム（緑の小さな四角錐）の表示/非表示。<BR>カメラが通過した位置・姿勢を示す |
| Show Graph | Covisibility Graph（キーフレーム間の青い線）の表示/非表示。<BR>共通特徴点が多いキーフレーム同士が接続される |
| Show Inertial Graph | IMU慣性グラフの表示/非表示。<BR>単眼SLAMのみの場合は無効 |
| Localization Mode | **重要**: ONにするとマッピングを停止し、既存マップへのローカライゼーションのみ行う。<BR>メモリ増加を抑えたい場合に有効 |

### 安定させるコツ

- カメラを**ゆっくり**動かす（急激な動作でトラッキングロストが発生）
- テクスチャの豊富な場所（キーボード、本棚など）を向ける
- 急激な回転を避け、**平行移動**を優先する

---

## トラブルシューティング

### YAML パースエラー（BOM問題）

```txt
Premature end of file while trying to read value.
```

→ YAMLファイルの先頭に UTF-8 BOM（`ef bb bf`）が含まれています。手順8.1の`printf`コマンドでファイルを再作成してください。

### `WAITING FOR IMAGES` のまま動かない

1. カメラノードが起動しているか確認:

   ```bash
   docker exec <CONTAINER_ID> bash -c "source /opt/ros/humble/setup.bash && ros2 topic list | grep image"
   ```

2. QoS の確認:

   ```bash
   docker exec <CONTAINER_ID> bash -c "source /opt/ros/humble/setup.bash && ros2 topic info /image_raw --verbose"
   ```

3. カメラノードを `use_sensor_data_qos:=true` で起動する（手順11参照）

### シンボリックリンクが見つからない

```bash
docker exec <CONTAINER_ID> bash -c "
  ls /root/colcon_ws/install/orb_slam3_ros2_wrapper/share/orb_slam3_ros2_wrapper/params/orb_slam3_params/
"
```

c270_mono.yaml が存在しない場合は手順10を再実行してください。

### Tracking LOST が頻発する

単眼SLAMの特性上、急激な動きや特徴点の少ない環境では発生します。`Relocalized!!` が表示されれば自動復帰します。頻発する場合はキャリブレーション精度を確認してください。

---

## パフォーマンス参考値

| 項目 | 値 |
| ---- | -- |
| トラッキング周波数 | 25〜30 fps |
| CPU使用率 | 約150〜157% （2コア相当） |
| RAM使用量 | 約1,500〜1,650 MB |

---

## 関連ファイル

| ファイル | 用途 |
| -------- | ---- |
| `orb_slam3_ros2_wrapper/params/orb_slam3_params/c270_mono.yaml` | カメラキャリブレーション・ORB設定 |
| `orb_slam3_ros2_wrapper/params/ros_params/c270-mono-ros-params.yaml` | ROS2トピック・フレーム設定 |
| `docker-compose.yml` | コンテナ定義（NVIDIAランタイム設定） |
