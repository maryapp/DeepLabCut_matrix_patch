rm -r TEST*
rm -r multi_mouse*
cd ..
pip uninstall deeplabcut
python3 setup.py sdist bdist_wheel
pip install dist/deeplabcut-2.2b5-py3-none-any.whl

cd examples
python3 testscript.py
python3 testscript_3d.py
python3 testscript_mobilenets.py
python3 testscript_multianimal.py
