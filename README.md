# OAK-D data recording tools

## Usage

 1. Setup SDK and install Python pacakges in a virtualenv (see below)
 2. Activate virtualenv: `source bin/venv/activate`
 3. Record `python record.py`. Stop with Ctrl+C
 4. Get the output from a timestamped subfolder in `output/`

See `python record.py --help` for more options.

Note that it does not actually seem possible to record all three cameras at full resolution at 25 FPS, even though the examples indicate that it's possible.
In practice, frames will start to be dropped heavily from the stereo global shutter cameras if the system is overwhelmed so be careful with the `--color` and `--color_resolution` options. In particular, do not set color resolution to 4K if you are also planning to record stereo data from the gray cameras.
The manual exposure control seems to also be buggy (may be just this code) if `--color` is used. You have been warned.

Note: It's possible for the device to end up in a bad state so that the recording script fails to produce synchronized stereo output. In that case, try unplugging and replugging the device USB chord.

## OAK-D SDK installation instructions

The driver / SDK software installation instructions can be found here https://docs.luxonis.com/projects/api/en/latest/install.
If you do not like the suggested `wget ... | sudo bash -` method, just check the contents of the script, which lists the packages.
Tested platform-specific instructions below.

### Docker

Seemed to work out-of-the-box on Ubuntu 20 and Debian Stretch using [official instructions](https://docs.luxonis.com/projects/api/en/latest/install/#docker).
Recording can be done through Docker as:

    docker pull luxonis/depthai-library
    ./docker-record.sh

The above command is a wrapper for `record.py` and has the same command line arguments.
Due to how Docker mounts work, the produced `output` folder may be owned by the wrong user ID and you may have to use `sudo` to, e.g., delete recordings.

### Ubuntu

**USB settings**.

    # Allow all users to read and write to Myriad X devices
    echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
    sudo udevadm control --reload-rules && sudo udevadm trigger

**System packages**. Note that these are mostly dependencies of OpenCV which you may have already

    sudo apt install python3 python3-pip udev cmake git \
      build-essential \
      libgtk2.0-dev \
      pkg-config \
      libavcodec-dev \
      libavformat-dev \
      libswscale-dev \
      python-dev \
      libtbb2 \
      libtbb-dev \
      libjpeg-dev \
      libpng-dev \
      libtiff-dev \
      libdc1394-22-dev \
      ffmpeg \
      libsm6 \
      libxext6 \
      libgl1-mesa-glx

The script also suggested `python3-numpy` but I wouldn't recommend to install it from `apt`
and added it to the below list of Python packages too.

**Virtualenv**. Optional but recommended. If you want to avoid [this](https://xkcd.com/1987/),
use separate virtualenvs for separate projects.

    virtualenv venv
    source venv/bin/activate

**Python packages**

    pip install -r requirements.txt

## OAK-D SDK examples (Python)

To get to know OAK-D, it may help to look at their example collection, which is quite good. After cloning

    git clone https://github.com/luxonis/depthai-python.git

they can be run in the virtualenv (or Docker) as, e.g.,

    cd depthai-python/examples
    python rgb_preview.py

## OAK-D SDK examples (C++)

    git clone --recursive https://github.com/luxonis/depthai-core
    cd depthai-core
    cmake -H. -Bbuild -DCMAKE_INSTALL_PREFIX=`pwd`/../depthai-core-install
    # Library
    cmake --build build
    cmake --build build --target install

    # Examples
    cmake -H. -Bbuild \
      -D DEPTHAI_TEST_EXAMPLES=ON \
      -D DEPTHAI_BUILD_TESTS=ON \
      -D DEPTHAI_BUILD_EXAMPLES=ON \
      -DOpenCV_DIR=/full/path/to/mobile-cv-suite/build/host/lib/cmake/opencv4

    cmake --build build
    cd build/examples
    ./mono_preview
