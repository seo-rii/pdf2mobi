from tqdm import tqdm
from PIL import Image, ImageDraw
import img2pdf
import os
import io
from multiprocessing import Pool, Manager, freeze_support
from itertools import product

size_width = 1072
size_height = 1448


def makeImgFromPdf(arg):
    (epiNo, title) = arg
    #pdf = open(title + "/" + title + "_" + str(epiNo) + ".pdf", "rb").read()
    pdf = open(title + "/" + title + "_" + ("000" + str(epiNo))[-3:] + ".pdf", "rb").read()

    startmark = b"\xff\xd8"
    startfix = 0
    endmark = b"\xff\xd9"
    endfix = 2
    i = 0
    njpg = 0
    orginalImage = []
    while True:
        istream = pdf.find(b"stream", i)
        if istream < 0:
            break
        istart = pdf.find(startmark, istream, istream + 20)
        if istart < 0:
            i = istream + 20
            continue
        iend = pdf.find(b"endstream", istart)
        if iend < 0:
            raise Exception("Didn't find end of stream!")
        iend = pdf.find(endmark, iend - 20)
        if iend < 0:
            raise Exception("Didn't find end of JPG!")
        istart += startfix
        iend += endfix
        jpg = pdf[istart:iend]
        orginalImage.append(io.BytesIO())
        orginalImage[-1].write(jpg)
        njpg += 1
        i = iend
    margin = []
    marginColor = []
    imList = []
    canvas = Image.new("L", (size_width, 0))
    marginColor.append(0)
    for i in orginalImage:
        try:
            im = Image.open(i)
            im = im.resize((size_width, int(im.size[1] / im.size[0] * size_width)))
        except:
            pass
        new_canvas = Image.new("L", (size_width, canvas.size[1] + im.size[1]))
        new_canvas.paste(im=canvas, box=(0, 0))
        new_canvas.paste(im=im, box=(0, canvas.size[1]))
        canvas = new_canvas
        while canvas.size[1] > size_height:
            oFl = True
            for y in range(canvas.size[1]):
                pix = canvas.getpixel((0, y))
                fl = True
                for x in range(size_width):
                    if not pix + 5 >= canvas.getpixel((x, y)) >= pix - 5:
                        fl = False
                        break
                if fl:
                    if y > 30:
                        tCanvas = canvas.crop((0, 0, size_width, y - 1))
                        if len(margin) > 0:
                            if margin[-1] < 10:
                                tImg = Image.new("L", (size_width, imList[-1].size[1] + margin[-1] + tCanvas.size[1]))
                                tImg.paste(im=imList[-1], box=(0, 0))
                                tImg.paste(im=tCanvas, box=(0, imList[-1].size[1] + margin[-1]))
                                imList[-1] = tImg
                                margin[-1] = 0
                                marginColor[-2] = pix
                            else:
                                imList.append(tCanvas)
                                margin.append(0)
                                marginColor.append(pix)
                                marginColor.append(0)
                        else:
                            imList.append(tCanvas)
                            margin.append(0)
                            marginColor.append(pix)
                            marginColor.append(0)
                    else:
                        if len(margin) > 0:
                            margin[-1] += y + 1
                    marginColor[-1] = pix
                    canvas = canvas.crop((0, y + 1, size_width, canvas.size[1]))
                    oFl = False
                    break
            if oFl:
                imList.append(canvas)
                marginColor[-1] = canvas.getpixel((0, 0))
                marginColor.append(marginColor[-1])
                marginColor.append(0)
                margin.append(0)
                canvas = Image.new("L", (size_width, 0))

    imList.append(canvas)
    marginColor.append(marginColor[-1])

    for i in range(0, len(imList)):
        if imList[i].size[1] > size_height:
            new_canvas = Image.new("L", (size_width, size_height), color=marginColor[i * 2])
            new_canvas.paste(imList[i].resize((int(imList[i].size[0] / imList[i].size[1] * size_height), size_height)),
                             box=(int((int(size_width - imList[i].size[0] / imList[i].size[1] * size_height)) / 2), 0))
            imList[i] = new_canvas

    cnt = 0
    canvas = imList[0]
    canvasBeforeColor = marginColor[0]
    canvasAfterColor = marginColor[1]

    try:
        os.makedirs(title + '/tmp/' + str(epiNo) + '/')
    except:
        pass
    for i in range(1, len(imList)):
        beforeMarginColor = marginColor[i * 2]
        afterMarginColor = marginColor[i * 2 + 1]
        if canvas.size[1] + margin[i - 1] + imList[i].size[1] <= size_height:
            new_canvas = Image.new("L", (size_width, canvas.size[1] + margin[i - 1] + imList[i].size[1]))
            new_canvas.paste(im=canvas, box=(0, 0))
            draw = ImageDraw.Draw(new_canvas)
            for y in range(canvas.size[1], canvas.size[1] + margin[i - 1]):
                nowColor = int((canvasAfterColor - beforeMarginColor) * (y - canvas.size[1]) / (
                        margin[i - 1] - 1) + beforeMarginColor)
                draw.line([(0, y), (size_width - 1, y)], nowColor, width=1)
            new_canvas.paste(im=imList[i], box=(0, canvas.size[1] + margin[i - 1]))
            canvasAfterColor = afterMarginColor
            canvas = new_canvas
        else:
            save_canvas = Image.new("L", (size_width, size_height))
            draw = ImageDraw.Draw(save_canvas)
            draw.rectangle(((0, 0), (size_width, int((size_height - canvas.size[1]) / 2) + 1)), fill=canvasBeforeColor)
            draw.rectangle(
                ((0, int((size_height + canvas.size[1]) / 2) - 1), (size_width, size_height)), fill=canvasAfterColor)
            save_canvas.paste(im=canvas, box=(0, int((size_height - canvas.size[1]) / 2)))

            for x in range(1, save_canvas.size[0]):
                for y in range(1, save_canvas.size[1]):
                    value = pow(save_canvas.getpixel((x, y)) / 255, (1 / 0.7)) * 255
                    if value >= 255:
                        value = 255
                    save_canvas.putpixel((x, y), int(value))
            save_canvas.save(title + '/tmp/' + str(epiNo) + '/' + str(cnt) + '.jpeg', format='jpeg', quality=30)
            cnt += 1

            canvas = imList[i]
            canvasBeforeColor = beforeMarginColor
            canvasAfterColor = afterMarginColor

    try:
        for x in range(1, canvas.size[0]):
            for y in range(1, canvas.size[1]):
                value = pow(canvas.getpixel((x, y)) / 255, (1 / 0.7)) * 255
                if value >= 255:
                    value = 255
                canvas.putpixel((x, y), int(value))
        canvas.save(title + '/tmp/' + str(epiNo) + '/' + str(cnt) + '.jpeg', format='jpeg', quality=30)
    except:
        cnt-=1

    try:
        os.makedirs(title + '/res/')
    except:
        pass
    if cnt>0:
        with open(title + '/res/' + str(epiNo) + '화.pdf', "wb") as f:
            f.write(img2pdf.convert(
                [(title + '/tmp/' + str(epiNo) + '/' + str(k) + '.jpeg') for k in range(cnt + 1)]))


if __name__ == '__main__':
    freeze_support()
    print('Title : ')
    title = input()
    print('EpisodeNo : ')
    episodeNo = int(input())
    print('Start From : ')
    begin = int(input())

    os.system('cls')
    mainEpisode = range(begin, episodeNo + 1)

    manager = Manager()

    with Pool(processes=8) as p:
        max_ = episodeNo
        with tqdm(total=max_) as pbar:
            for i, _ in enumerate(
                    p.imap_unordered(makeImgFromPdf, product(range(1, episodeNo + 1), [title]))):
                pbar.update()
