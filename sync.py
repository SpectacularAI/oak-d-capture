"""
Optional IMU-camera sync module. These arguments can be added to record.py
"""
import threading, json, time

MIN_SYNC_T = 3
BASELINE_MULT = 2
PLOT_FREQ = 0.5

def external_imu_reader(file, imuSync):
    def jsonl_reader():
        try:
            for line in file:
                d = json.loads(line)
                s = d.get('sensor', None)
                if s is None: continue
                imuSync.pushExternalSensor(d['time'], s['type'], s['values'])
        except KeyboardInterrupt:
            pass
        print('IMU reader thread stopped nicely')
    return threading.Thread(target=jsonl_reader)

def to_sync_signal(name, vals):
    import numpy as np
    if not 'accelerometer' in name: return None
    return np.linalg.norm(vals)

def plotter(plotType):
    import matplotlib.pyplot as plt
    fig = plt.figure()
    syncPlot = plotType == 'sync'

    tPrev = None
    def plot(t, data, baselines = None, syncData = None):
        nonlocal tPrev
        if baselines is None: baselines = {}
        if syncData is None:
            if syncPlot: return
            syncData = {}

        if tPrev is not None and t < tPrev + PLOT_FREQ:
            return

        if syncPlot and tPrev is not None: return
        tPrev = t

        plt.figure(fig.number)
        plt.clf()
        max_t = 0
        for k, v in data.items():
            sensors = { x[2] for x in v }
            if len(v) == 0: continue
            for s in sensors:
                ss = [x for x in v if x[2] == s]
                offset = syncData.get(k, 0)
                # print(k, offset)
                tt = [x[1] + offset for x in ss]
                max_t = max(max_t , max(tt))
                plt.plot(tt, [x[3] for x in ss], label='%s %s' % (k, s))

        min_t = max_t - PLOT_FREQ
        tlim = [min_t, max_t]
        for k in data.keys():
            if k not in baselines: continue
            m, s = baselines[k]
            #plt.plot(tlim, [m, m], 'c')
            plt.plot(tlim, [m+s, m+s], 'c--')
            plt.plot(tlim, [m-s, m-s], 'g--')

        plt.legend()
        if not syncPlot: plt.xlim(tlim)
        plt.draw()
        reps = 1
        if syncPlot: reps = 3 # stupid workaround
        for i in range(reps):
            plt.draw()
            plt.pause(0.0001)

    return plot

def compute_baselines(data):
    import numpy as np
    r = {}
    for k, a in data.items():
        if len(a) > 0:
            vv = np.array([v[-1] for v in a])
            m = np.mean(vv)
            s = max(np.max(vv - m), m*0.01)*BASELINE_MULT
            r[k] = (m, s)
    return r

def merge_baselines(b1, b2):
    r = {}
    ALPHA = 0.7
    smooth = lambda x, prev: ALPHA*x + (1-ALPHA)*prev
    for k, (m, s) in b2.items():
        m1, s1 = b1.get(k, (m, s))
        r[k] = (smooth(m, m1), smooth(s, s1))
    return r

def try_sync(data, baselines):
    import numpy as np
    t = {}
    print('READY, waiting for sync cue')
    for k, a in data.items():
        if k not in baselines:
            #print('no %s' % k)
            return None
        m, s = baselines[k]
        vv = np.array([v[-1] for v in a])
        over = np.abs(vv - m) > s
        if not np.any(over):
            # print('%s not over threshold' % k)
            return None
        t[k] = a[np.flatnonzero(over)[0]][1]

    main = 'main'
    if 'main' not in baselines: main = 'cam'
    return { k: t[main] - t[k] for k in t.keys() if k != main }

class ImuSyncrhonizer:
    def __init__(self,
        external_imu_file,
        plot,
        sync_imu_and_camera,
        sync_window_length_sec):

        self.syncWindow = {
            'main': []
        }

        self.externalSamples = []
        if external_imu_file is None:
            self.externalReader = None
            self.externalImuFile = None
        else:
            self.externalImuFile = external_imu_file
            self.externalReader = external_imu_reader(external_imu_file, self)
            self.externalReader.start()
            self.syncWindow['ext'] = []

        self.syncWindowLengthSec = sync_window_length_sec

        self.offsetCam = 0
        self.offsetExtImu = 0
        self.syncCam = sync_imu_and_camera
        self.syncImu = sync_window_length_sec > 0 and external_imu_file is not None

        if self.syncCam:
            self.syncWindow['cam'] = []

        self.plotter = None
        if plot is not None:
            self.plotter = plotter(plot)

        self.t0 = None
        self.prevMat = None
        self.flow = None
        self.lastSyncT = None
        self.baselines = None
        self.syncSuccess = not self.syncCam and not self.syncImu
        self.syncResult = None

    def pushFrame(self, t, frame):
        if not self.syncCam: return
        import cv2
        import numpy as np
        SCALE = 0.1
        mat = frame.getCvFrame()
        #mat = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
        mat = cv2.resize(mat, (int(mat.shape[1] * SCALE), int(mat.shape[0] * SCALE)), interpolation=cv2.INTER_AREA)
        if self.prevMat is not None:
            self.flow = cv2.calcOpticalFlowFarneback(self.prevMat, mat, self.flow, 0.5, 3, 15, 3, 5, 1.2, 0) # no sure about the params
            meanFlow = np.linalg.norm([np.mean(self.flow[..., i]) for i in range(2)])
            MIN_FLOW = 0.1 # hack for baseline scaling
            meanFlow += MIN_FLOW
            self.syncWindow['cam'].append((t, t, 'camFlow', meanFlow))

        self.prevMat = mat

    def pushSensor(self, t, name, xyz):
        if self.t0 is None: self.t0 = t
        if self.syncImu:
            syncS = to_sync_signal(name, xyz)
            if syncS is not None:
                self.syncWindow['main'].append((t, t, name + '-sync', syncS))

        extOut = []
        for t1, name1, xyz1 in self._pollExternalSensors():
            if self.syncImu or self.syncCam:
                syncS = to_sync_signal(name1, xyz1)
                if syncS is not None:
                    self.syncWindow['ext'].append((t, t1, name1 + '-sync', syncS))
            if self.ready():
                extOut.append((t1 + self.offsetExtImu, name1, xyz1))

        # assume approx sorted
        t_min = t - self.syncWindowLengthSec
        n_removed = 0
        for q in self.syncWindow.values():
            while len(q) > 0 and q[0][0] < t_min:
                q.pop(0)
                n_removed += 1

        if n_removed > 0:
            self._trySync(t)

        if self.plotter is not None:
            self.plotter(t, self.syncWindow, self.baselines, self.syncResult)

        return extOut

    def pushExternalSensor(self, t, name, xyz):
        with threading.Lock():
            self.externalSamples.append((t, name, xyz))

    def _pollExternalSensors(self):
        if self.externalReader is None: return []
        with threading.Lock():
            r = self.externalSamples[:]
            self.externalSamples.clear()
            return r

    def _trySync(self, t):
        if self.syncSuccess: return
        if self.lastSyncT is not None and t < self.lastSyncT + self.syncWindowLengthSec:
            return
        self.lastSyncT = t

        b = compute_baselines(self.syncWindow)
        if self.baselines is None:
            self.baselines = b
        else:
            if t - self.t0 > MIN_SYNC_T:
                syncResult = try_sync(self.syncWindow, self.baselines)
                if syncResult is not None:
                    self.syncSuccess = True
                    print('sync results', syncResult)
                    if 'ext' in syncResult:
                        self.offsetExtImu = syncResult['ext']
                    if 'cam' in syncResult:
                        self.offsetCam = syncResult['cam']
                    self.syncResult = syncResult
                    if self.plotter is not None:
                        self.plotter(t, self.syncWindow, self.baselines, self.syncResult)

            self.baselines = merge_baselines(self.baselines, b)

    def getCloseables(self):
        return [self]

    def close(self):
        if self.externalImuFile is not None:
            print('closing external IMU file')
            self.externalImuFile.close()
            self.externalImuFile = None

    def ready(self):
        return self.syncSuccess

def arg_parser(help=False):
    import argparse
    p = argparse.ArgumentParser(__doc__, add_help=help)
    p.add_argument('--sync_imu_and_camera', action='store_true')
    p.add_argument('--plot', choices=["sync", "all"], help='Plot IMU and sync data')
    p.add_argument('--sync_window_length_sec', default=3, type=float)
    p.add_argument('--external_imu_file', type=argparse.FileType('r'))
    return p

def parse_known():
    args, others = arg_parser().parse_known_args()
    return args, others

if __name__ == '__main__':
    args = arg_parser(help=True).parse_args()
