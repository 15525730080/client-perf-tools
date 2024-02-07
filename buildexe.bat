pyinstaller --onefile --add-data "performancetest;performancetest" --add-data "performancetest/web/test_result/index.html;performancetest/web/test_result"  --add-data "airtest path;airtest" performancetest/web/main.py -i icon

python setup.py sdist bdist_wheel

python -m twine upload dist/*
