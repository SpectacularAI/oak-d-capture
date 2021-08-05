#!/usr/bin/env python3
# based on https://github.com/luxonis/depthai-python/blob/9e21b38f49cfb9282b8bd93cb811a3e01709d502/examples/13_encoding_max_limit.py
"""
Record video and IMU data from an OAK-D.

See the file NOTICE for copyright and license information.
"""
import depthai as dai
import json, os, sys

COLOR_RESOLUTIONS = {
    'THE_1080_P': (1920, 1080),
    'THE_4_K': (3840, 2160),
    'THE_12_MP': (4056, 3040) # this only works for still images
}

GRAY_RESOLUTIONS = {
    'THE_720_P': (1280, 720),
    'THE_800_P': (1280, 800),
    'THE_400_P': (640, 400)
}

IMU_TYPES = {
    'RAW': [dai.IMUSensor.ACCELEROMETER_RAW, dai.IMUSensor.GYROSCOPE_RAW],
    'UNCALIBRATED': [dai.IMUSensor.ACCELEROMETER, dai.IMUSensor.GYROSCOPE_UNCALIBRATED],
    'CALIBRATED': [dai.IMUSensor.ACCELEROMETER, dai.IMUSensor.GYROSCOPE_CALIBRATED],
}

class Camera:
    def __init__(self, pipeline, index, whichCam, resolution, control):
        self.index = index
        if whichCam == 'color':
            self.camera = pipeline.createColorCamera()
            self.resolution = COLOR_RESOLUTIONS[resolution]
            self.camera.setResolution(getattr(dai.ColorCameraProperties.SensorResolution, resolution))
            encoding = dai.VideoEncoderProperties.Profile.H265_MAIN
            streamSuffix = 'h265'
            self.cameraOut = self.camera.video
        else:
            self.camera = pipeline.createMonoCamera()
            self.resolution = GRAY_RESOLUTIONS[resolution]
            encoding = dai.VideoEncoderProperties.Profile.H264_MAIN
            streamSuffix = 'h264'
            self.cameraOut = self.camera.out
            if whichCam == 'left':
                self.camera.setBoardSocket(dai.CameraBoardSocket.LEFT)
            elif whichCam == 'right':
                self.camera.setBoardSocket(dai.CameraBoardSocket.RIGHT)
            else:
                assert(False)
            self.camera.setResolution(getattr(dai.MonoCameraProperties.SensorResolution, resolution))

        self.streamName = 've%dOut' % index
        self.encoder = pipeline.createVideoEncoder()
        self.encoder.setDefaultProfilePreset(self.resolution[0], self.resolution[1], self.camera.getFps(), encoding)

        # Our output file name settings
        self.streamFileName = 'video%d.%s' % (index, streamSuffix)
        self.outFileName = 'data'
        if index != 1: self.outFileName += str(index)
        self.outFileName += '.mp4'
        self.outputFile = None

        control.out.link(self.camera.inputControl)

    def link(self, pipeline, preview):
        out = pipeline.createXLinkOut()
        out.setStreamName(self.streamName)
        if preview:
            self.cameraOut.link(out.input)
        else:
            self.cameraOut.link(self.encoder.input)
            self.encoder.bitstream.link(out.input)

    def setupOutputQueue(self, dev, preview=False):
        if preview:
            blocking=False
            maxSize=4
        else:
            blocking=True
            maxSize=30
        self.outputQueue = dev.getOutputQueue(self.streamName, maxSize=maxSize, blocking=blocking)

    def openOutputFile(self, folder):
        self.fullStreamFilePath = os.path.join(folder, self.streamFileName)
        self.fullVideoPath = os.path.join(folder, self.outFileName)
        self.outputFile = open(self.fullStreamFilePath, 'wb')

    def close(self):
        if self.outputFile is not None:
            self.outputFile.close()
            self.outputFile = None
            cmd = "ffmpeg -framerate %d -i '%s' -c copy '%s'" % (self.camera.getFps(), self.fullStreamFilePath, self.fullVideoPath)
            print(cmd)
            os.system(cmd)
            os.remove(self.fullStreamFilePath)

class Imu:
    def __init__(self, pipeline, imu_freq, imu_report_batch, imu_max_batch, imu_type):
        # Define sources and outputs
        imu = pipeline.createIMU()
        xlinkOut = pipeline.createXLinkOut()

        xlinkOut.setStreamName("imu")

        imu.enableIMUSensor(IMU_TYPES[imu_type], imu_freq)
        # above this threshold packets will be sent in batch of X, if the host is not blocked and USB bandwidth is available
        imu.setBatchReportThreshold(imu_report_batch)
        # maximum number of IMU packets in a batch, if it's reached device will block sending until host can receive it
        # if lower or equal to batchReportThreshold then the sending is always blocking on device
        # useful to reduce device's CPU load  and number of lost packets, if CPU load is high on device side due to multiple nodes
        imu.setMaxBatchReports(imu_max_batch)

        # Link plugins IMU -> XLINK
        imu.out.link(xlinkOut.input)

        self.imu = imu # necessary?

    def setupOutputQueue(self, dev):
        # Output queue for imu bulk packets
        self.outputQueue = dev.getOutputQueue(name="imu", maxSize=50, blocking=False)

    def poll(self, jsonlOut, t0):
        def writeSensor(sample, name):
            if t0 is None: return
            t = sample.timestamp.get().total_seconds() - t0
            vals = [sample.x, sample.y, sample.z]
            jsonlOut.write(json.dumps({
                'time': t,
                'sensor': {
                    'type': name,
                    'values': vals
                }
            })+'\n')

        while self.outputQueue.has():
            for imuPacket in self.outputQueue.get().packets:
                writeSensor(imuPacket.acceleroMeter, 'accelerometer')
                writeSensor(imuPacket.gyroscope, 'gyroscope')

class StereoSynchronizer:
    def __init__(self, n):
        self.n = n
        self.queues = [[] for _ in range(n)]

    def push(self, index, seqNo, obj):
        self.queues[index].append([seqNo, obj])
        #for q in self.queues:
        #    while len(q) > 0 and q[0][0] < seqNo:
        #        print('warn: dropped frame from cam %d with seqNo %d' % (index, q[0][0]))
        #        q.pop(0)

    def has(self):
        return all([len(q) > 0 for q in self.queues])

    def get(self, ignore_warnings=False):
        if len({ q[0][0] for q in self.queues if len(q) > 0 }) != 1 and not ignore_warnings:
            print('warn: unexpected sequence numbers')
            #for q in self.queues: q.clear()
            #return None
        return [q.pop(0)[1] for q in self.queues]

def curTimeIso8601Dash():
    import datetime
    return datetime.datetime.now().replace(microsecond=0).isoformat().replace(':', '')

def manualExposure(controlQueue, expTimeMs, sensIso):
    if expTimeMs <= 0: return
    expTimeUs = int(round(expTimeMs * 1000))
    MIN_ISO = 100
    MAX_ISO = 1600
    MIN_EXP_TIME_US = 1
    MAX_EXP_TIME_US = 33000
    assert(sensIso >= MIN_ISO)
    assert(sensIso <= MAX_ISO)
    assert(expTimeUs >= MIN_EXP_TIME_US)
    assert(expTimeUs <= MAX_EXP_TIME_US)
    assert(sensIso > 0)
    ctrl = dai.CameraControl()
    ctrl.setManualExposure(expTimeUs, sensIso)
    controlQueue.send(ctrl)

def manualFocus(controlQueue, focus):
    if focus < 0: return
    assert(focus >= 0 and focus <= 255)
    ctrl = dai.CameraControl()
    #ctrl.setAutoFocusMode(dai.RawCameraControl.AutoFocusMode.OFF)
    ctrl.setManualFocus(focus)
    controlQueue.send(ctrl)

def record(output_root_folder,
    gray_fps, color_fps,
    gray_focus, color_focus,
    mono, color,
    gray_resolution, color_resolution,
    gray_iso, color_iso,
    gray_exp_ms, color_exp_ms,
    keep_t0, preview,
    imu_freq, imu_report_batch, imu_max_batch, imu_type,
    discard_other_imu, preview_imu, sort):

    if not preview:
        folder = os.path.join(output_root_folder, curTimeIso8601Dash())
        os.makedirs(folder, exist_ok=True)

    pipeline = dai.Pipeline()

    # Create and link control input
    controlInputGray = pipeline.createXLinkIn()
    controlInputGray.setStreamName('controlGray')
    controlInputColor = pipeline.createXLinkIn()
    controlInputColor.setStreamName('controlColor')

    if imu_freq <= 0:
        imu = None
        print('No IMU')
    else:
        imu = Imu(pipeline, imu_freq, imu_report_batch, imu_max_batch, imu_type)

    cameras = []

    def buildColCam(index):
        cam = Camera(pipeline, index, 'color', color_resolution, controlInputColor)
        cam.link(pipeline, preview)
        if color_fps > 0:
            cam.camera.setFps(color_fps)
            cam.encoder.setFrameRate(color_fps)
        return cam

    def buildGrayCam(index, leftOrRight):
        cam = Camera(pipeline, index, leftOrRight, gray_resolution, controlInputGray)
        cam.link(pipeline, preview)
        if gray_fps > 0:
            cam.camera.setFps(gray_fps)
            cam.encoder.setFrameRate(gray_fps)
        return cam

    if mono:
        if color:
            cameras = [[buildColCam(1)]]
        else:
            cameras = [[buildGrayCam(1, 'left')]]
    else:
        cameras = [[buildGrayCam(1, 'left'), buildGrayCam(2, 'right')]]
        if color:
            cameras.append([buildColCam(3)])

    flatCameraList = []
    for cameraSet in cameras:
        for camera in cameraSet:
            flatCameraList.append(camera)

    with dai.Device(pipeline) as dev:
        for camera in flatCameraList: camera.setupOutputQueue(dev, preview)
        if imu is not None: imu.setupOutputQueue(dev)
        grayControlQueue = dev.getInputQueue('controlGray')
        colorControlQueue = dev.getInputQueue('controlColor')
        try:
            closeList = []

            dev.startPipeline()
            print("Press Ctrl+C to stop...")

            manualExposure(grayControlQueue, gray_exp_ms, gray_iso)
            manualExposure(colorControlQueue, color_exp_ms, color_iso)
            manualFocus(grayControlQueue, gray_focus)
            manualFocus(colorControlQueue, color_focus)

            inputs = [(cs, StereoSynchronizer(len(cs))) for cs in cameras]

            jsonlOutFileName = None
            if preview:
                if preview_imu:
                    jsonlOut = sys.stdout
                else:
                    jsonlOut = open('/dev/null', 'w')
                    closeList.append(jsonlOut)
            else:
                for camera in flatCameraList: camera.openOutputFile(folder)
                closeList = flatCameraList[:]
                jsonlOutFileName = os.path.join(folder, 'data.jsonl')
                jsonlOut = open(jsonlOutFileName, 'wt')
                closeList.append(jsonlOut)

            t0 = None
            if keep_t0:
                t0 = 0

            storedFrameNumber = 1
            while True:
                if imu is not None: imu.poll(jsonlOut, t0)
                for cameraSet, synchronizer in inputs:
                    for idx, camera in enumerate(cameraSet):
                        q = camera.outputQueue
                        if q.has():
                            frame = q.get()
                            #print(frame)
                            if t0 is None:
                                t0 = frame.getTimestamp().total_seconds()
                            synchronizer.push(idx, frame.getSequenceNum(), [frame, camera])

                    if not synchronizer.has(): continue
                    frames = synchronizer.get(ignore_warnings=preview)
                    if frames is None: continue

                    meta = []
                    seqNums = { frame.getSequenceNum() for frame, _ in frames }
                    #assert(len(seqNums) == 1)
                    #assert(len({ frame.getTimestamp() for frame, _ in frames }) == 1)
                    assert(len(frames) > 0)
                    for frame, camera in frames:
                        if preview:
                            import cv2
                            cv2.imshow(camera.streamName, frame.getCvFrame())
                            if cv2.waitKey(1) == ord('q'): return
                        else:
                            # must write all frames
                            frame.getData().tofile(camera.outputFile)

                        d = {
                            'cameraInd': camera.index - 1,
                            'time': frame.getTimestamp().total_seconds() - t0,
                            'number': frame.getSequenceNum() # keep extra sequence number for debugging
                        }
                        meta.append(d)

                    if not preview:
                        jsonlOut.write(json.dumps({
                            'time': meta[0]['time'],
                            'frames': meta,
                            'number': storedFrameNumber
                        })+'\n')

                        storedFrameNumber += 1

        except KeyboardInterrupt:
            for closeable in closeList:
                closeable.close()

            if sort and jsonlOutFileName is not None:
                import sort_jsonl
                sort_jsonl.sort_jsonl_by(jsonlOutFileName, jsonlOutFileName)

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(__doc__.strip() + '\n')
    p.add_argument('--color', action='store_true',
        help='record also color video (as camera 3) or if mono=True, record only color video as camera 1')
    p.add_argument('--mono', action='store_true')
    p.add_argument('--color_resolution', choices=COLOR_RESOLUTIONS.keys(), default='THE_1080_P')
    p.add_argument('--gray_resolution', choices=GRAY_RESOLUTIONS.keys(), default='THE_800_P')
    p.add_argument('--color_iso', type=int, default=800, help='ISO sensitivity used with manual exposure')
    p.add_argument('--gray_iso', type=int, default=800)
    p.add_argument('--color_exp_ms', type=float, default=-1, help='If set to a positive value, enables fixed manual exposure time (in milliseconds)')
    p.add_argument('--gray_exp_ms', type=float, default=-1)
    p.add_argument('--gray_fps', type=int, default=-1)
    p.add_argument('--color_fps', type=int, default=-1)
    p.add_argument('--gray_focus', type=int, default=-1)
    p.add_argument('--color_focus', type=int, default=-1)
    p.add_argument('-o', '--output_root_folder', default='output')
    p.add_argument('--keep_t0', action='store_true', help='keep original timestamps (do not set first frame ts to 0)')
    p.add_argument('-p', '--preview', action='store_true', help='do not write data, but show the video streams on screen instead')
    p.add_argument('--imu_freq', type=int, default=500, help='IMU frequency (set to 0 to disable IMU)')
    p.add_argument('--imu_report_batch', type=int, default=5, help='IMU min batch size')
    p.add_argument('--imu_max_batch', type=int, default=100, help='IMU max batch size (device will block if reached)')
    p.add_argument('--imu_type', choices=IMU_TYPES.keys(), default='UNCALIBRATED')
    p.add_argument('--discard_other_imu', action='store_true')
    p.add_argument('--preview_imu', action='store_true', help='Print IMU data to stdout in --preview')
    p.add_argument('--sort', action='store_true', help='sort JSONL output (can help with ext IMUs)')
    args = p.parse_args()

    record(**vars(args))
