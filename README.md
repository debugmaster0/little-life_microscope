
Little Life is a microscope companion app that captures live camera frames and uses an LLM to describe what’s visible in biological or material samples. It’s designed for hobbyists, classrooms, and curious people who want interpretive feedback on microscope imagery.

Quick Start
###########
git clone https://github.com/debugmaster0/little-life.git
cd little-life
./setup_venv.sh
source .venv/bin/activate
PYTHONPATH=src python -m littlelife.app


To use the identify function you will need an open ai key.
Create an account, get a key, and buy a couple tokens for api requests (it's cheap)

Create a `.env` file in the project root:

OPENAI_API_KEY="sk-..."
CAMERA_ENABLED=1
CAMERA_DEVICE=/dev/video4 #This may change depending on how your computer sees your camera. 
CAMERA_WIDTH=1280
CAMERA_HEIGHT=960

On Linux, cameras appear as /dev/video*
Use v4l2-ctl --list-devices to find them
Set either:
CAMERA_DEVICE=/dev/video4, or
CAMERA_INDEX=4
If the app hangs on startup, the camera index is likely wrong
Some cameras expose multiple /dev/video* nodes
Parallels / VM setups may enumerate devices differently
On macOS, the AVFoundation backend is different and currently untested in this repo version


This project is currently tested and supported on Ubuntu Linux.
macOS support is experimental and may require changes to camera backends.
Windows has not been tested.