FROM python:3.11

WORKDIR /usr/src/app

RUN apt-get update && apt-get install libgl1 tesseract-ocr imagemagick bc xclip -y
RUN apt-get -y install fonts-noto-cjk

COPY src/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# Install langs
RUN apt-get install -y tesseract-ocr-jpn tesseract-ocr-jpn-vert tesseract-ocr-chi-sim tesseract-ocr-chi-sim-vert tesseract-ocr-chi-tra

RUN wget https://github.com/tesseract-ocr/tessdata_best/raw/main/jpn_vert.traineddata && \
    cp jpn_vert.traineddata /usr/share/tesseract-ocr/5/tessdata/jpn_vert_alt.traineddata

COPY src .

# CMD [ "python", "./PrimextractorGUI.py" ]
