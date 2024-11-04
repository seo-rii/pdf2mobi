import os
from tqdm import tqdm
from PIL import Image, ImageDraw
from ebooklib import epub
import uuid
import io
from multiprocessing import Pool, Manager, freeze_support
from itertools import product

size_width = 1072
size_height = 1448


def makeImgFromPdf(arg):
    (imLi, epiNo, title) = arg
    pdf = open(title + "/" + title + "_" + str(epiNo) + ".pdf", "rb").read()
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
        im = Image.open(i)
        im = im.resize((size_width, int(im.size[1] / im.size[0] * size_width)))
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

    finalImageList = []
    canvas = imList[0]
    canvasBeforeColor = marginColor[0]
    canvasAfterColor = marginColor[1]
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
            finalImageList.append(save_canvas)
            canvas = imList[i]
            canvasBeforeColor = beforeMarginColor
            canvasAfterColor = afterMarginColor
    finalImageList.append(canvas)
    imgByteArr = []
    for i in finalImageList:
        for x in range(1, i.size[0]):
            for y in range(1, i.size[1]):
                value = pow(i.getpixel((x, y)) / 255, (1 / 0.7)) * 255
                if value >= 255:
                    value = 255
                i.putpixel((x, y), int(value))
        imgByteArr.append(io.BytesIO())
        i.save(imgByteArr[-1], format='jpeg', quality=30)
    tImgArr = imLi[epiNo - 1]

    imgSize = 0
    for i in imgByteArr:
        imgSize += i.getbuffer().nbytes
    tImgArr.append(imgSize)
    tImgArr.append(imgByteArr)
    imLi[epiNo - 1] = tImgArr


if __name__ == '__main__':
    freeze_support()
    print('Title : ')
    title = input()
    print('Author : ')
    author = input()
    print('EpisodeNo : ')
    episodeNo = int(input())
    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language('ko')
    book.add_author(author)
    book.add_metadata(None, 'meta', '', {'name': 'zero-gutter', 'content': 'true'})
    book.add_metadata(None, 'meta', '', {'name': 'zero-margin', 'content': 'true'})
    book.add_metadata(None, 'meta', '', {'name': 'book-type', 'content': 'comic'})
    book.add_metadata(None, 'meta', '', {'name': 'fixed-layout', 'content': 'true'})
    book.add_metadata(None, 'meta', '', {'name': 'original-resolution', 'content': '1072x1448'})
    book.add_metadata(None, 'meta', '', {'name': 'primary-writing-mode', 'content': 'horizontal-lr'})
    book.add_metadata(None, 'meta', '', {'name': 'region-mag', 'content': 'true'})
    book.add_metadata(None, 'meta', '', {'name': 'orientation-lock', 'content': 'portrait'})
    style = 'body {display: block;margin: 0;padding: 0;background-color:#000000;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)

    toc = []
    pages = []

    os.system('cls')
    mainEpisode = range(1, episodeNo + 1)

    manager = Manager()
    imgByteArrAll = manager.list([[]] * episodeNo)

    with Pool(processes=8) as p:
        max_ = episodeNo
        with tqdm(total=max_) as pbar:
            for i, _ in enumerate(
                    p.imap_unordered(makeImgFromPdf, product([imgByteArrAll], range(1, episodeNo + 1), [title]))):
                pbar.update()
    imgByteArrAll = list(imgByteArrAll)
    imgSizeSum = 0
    epubCount = 0
    for epiNo in mainEpisode:
        isFirstPage = True
        imgSizeSum += imgByteArrAll[epiNo - 1][0]
        if imgSizeSum > 1024 * 1024 * 100:
            epubCount += 1
            imgSizeSum = 0
            book.add_item(nav_css)
            book.spine = (pages)
            book.toc = toc

            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            epub.write_epub(title + '_' + str(epubCount) + '.epub', book, {})

            book = epub.EpubBook()
            book.set_identifier(str(uuid.uuid4()))
            book.set_title(title + '_' + str(epubCount + 1))
            book.set_language('ko')
            book.add_author(author)

            book.add_metadata(None, 'meta', '', {'name': 'zero-gutter', 'content': 'true'})
            book.add_metadata(None, 'meta', '', {'name': 'zero-margin', 'content': 'true'})
            book.add_metadata(None, 'meta', '', {'name': 'book-type', 'content': 'comic'})
            book.add_metadata(None, 'meta', '', {'name': 'fixed-layout', 'content': 'true'})
            book.add_metadata(None, 'meta', '', {'name': 'original-resolution', 'content': '1072x1448'})
            book.add_metadata(None, 'meta', '', {'name': 'primary-writing-mode', 'content': 'horizontal-lr'})
            book.add_metadata(None, 'meta', '', {'name': 'region-mag', 'content': 'true'})
            book.add_metadata(None, 'meta', '', {'name': 'orientation-lock', 'content': 'portrait'})
            style = 'body {display: block;margin: 0;padding: 0;background-color:#000000;}'
            nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)

            toc = []
            pages = []

        for i in imgByteArrAll[epiNo - 1][1]:
            newPage = epub.EpubHtml(file_name=str(uuid.uuid4()) + '.xhtml', lang='ko')
            epimg = epub.EpubImage()
            fileName = "img/image_%s.jpeg" % str(uuid.uuid4())
            epimg.file_name = fileName
            epimg.media_type = "image/jpeg"
            epimg.set_content(i.getvalue())
            book.add_item(epimg)
            newPage.content = u'<div style="text-align:center;top:0%;"><img width="1264" height="1015" src="' + fileName + u'" /> </div> '
            newPage.add_item(nav_css)
            newPage.title = title + " " + str(epiNo) + "화"
            book.add_item(newPage)
            pages.append(newPage)
            if isFirstPage:
                toc.append(newPage)
            isFirstPage = False

    book.add_item(nav_css)
    book.spine = (pages)
    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    if epubCount == 0:
        epub.write_epub(title + '.epub', book, {})
    else:
        epub.write_epub(title + '_' + str(epubCount + 1) + '.epub', book, {})
