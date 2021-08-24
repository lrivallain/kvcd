FROM python:3.8
RUN pip install kvcd
CMD kopf run -m kvcd.main --verbose