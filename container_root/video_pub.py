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

VIDEO_PATH = '/root/20250928_133344.MP4'
OUTPUT_W = 640
OUTPUT_H = 360
TARGET_FPS = 30.0  # 配信FPS（動画と同じ）

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
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.get_logger().info(
            f'動画: {w}x{h} @ {fps}fps, {total}フレーム ({total/fps:.1f}秒)'
        )
        self.get_logger().info(
            f'配信: {OUTPUT_W}x{OUTPUT_H} @ {TARGET_FPS}fps → /image_raw'
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

            frame_resized = cv2.resize(frame, (OUTPUT_W, OUTPUT_H))
            msg = self.bridge.cv2_to_imgmsg(frame_resized, encoding='bgr8')
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'camera'
            self.pub.publish(msg)

            frame_num += 1
            if frame_num % 150 == 0:
                self.get_logger().info(f'配信中: {frame_num}フレーム')

            # フレームレート制御
            elapsed = time.time() - t0
            sleep_t = interval - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

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
