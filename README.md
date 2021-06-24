# Simple Python Recording App

This app allow user to read the txt.file and control the recording process in an interface
Tested on Ubuntu 16.04, windows 10
![alt text](sample.JPG "screenshot of recorder in windows 10")

### Installation

```bash
conda create -n recorder python=3.8
conda activate recorder
conda install -c conda-forge pyqt5-sip -y
pip install pyyaml
pip install PyAudio
pip install numpy
pip install pyqtgraph
pip install PyQt5
```

### Configuration

```python
cp demo_setting.yaml current_setting.yaml
#update your current_setting.yaml
python recording_app.py
```