#!/usr/bin/python
# vim: set fileencoding=utf-8 :

ENTRIES_DIR = "./entries"
ATTACHMENTS_DIR = "./attachments"
TEMPLATE_DIR = "./templates"
ATTACHMENTS_URL = "/attachments"
ALLOWED_FROM_EMAILS = ["john@smith.com"]
IMAGE_ARTIST_COPYRIGHT = "John Smith"
THUMBSIZE = (400, 800)

### config over ###

import email.Parser
from uuid import uuid4
import htmlentitydefs
import sys
import os
import re

from Cheetah.Template import Template

import Image
import pyexiv2

# change to the directory where this script lives
if os.path.isdir(sys.path[0]):
	os.chdir(sys.path[0])
else:
	os.chdir(os.path.dirname(sys.path[0]))

# read local_config.py for config updates
if os.path.isfile("settings_local.py"):
	from settings_local import *

# code to generate a slug from the subject heading
# http://snipplr.com/view/26266/create-slugs-in-python/
def slugfy(text, separator):
	ret = ""
	for c in text.lower():
		try:
			ret += htmlentitydefs.codepoint2name[ord(c)]
		except:
			ret += c
	ret = re.sub("([a-zA-Z])(uml|acute|grave|circ|tilde|cedil)", r"\1", ret)
	ret = re.sub("\W", " ", ret)
	ret = re.sub(" +", separator, ret)
	return ret.strip()

# read the email in from stdin and parse it
p = email.Parser.Parser()
msg = p.parse(sys.stdin)

# check that the from address was an allowed one
correct_from_address = False
for a in ALLOWED_FROM_EMAILS:
	if a in msg['From']:
		correct_from_address = True

# a list of our binaries
binaries = []

# a list of tags to append
tags = ["blogblast"]

# the actual body of the message sent goes into this variable
message = ""

# the subject of the body
subject = msg["Subject"]

# filename of our text entry
entryfile = os.path.join(ENTRIES_DIR, slugfy(subject, "-") + ".txt")

# go ahead and separate all of the parts out
if correct_from_address:
	# loop through the attached message parts (files, etc)
	partcounter = 0
	for part in msg.walk():
		# we only care about the actual lowest single parts
		if part.get_content_maintype() == "multipart":
			continue
		
		# only count parts we care about
		partcounter += 1
		#print part.get_content_maintype()
		#print partcounter
		
		# get the file name of this file
		filename = part.get_param("name")
		if filename:
			# what kind of content is this?
			ctype = part.get_content_maintype()
			# get the file extension
			extension = os.path.splitext(filename)[1]
			# generate a new output filename
			uid = str(uuid4())
			outfilename = os.path.join(ATTACHMENTS_DIR, uid)
			# write this file out
			outfile = open(outfilename + extension, "wb")
			outfile.write(part.get_payload(decode=1))
			outfile.close()
			
			# if it's an image, rotate it to the correct orientation
			# and make a thumbnail
			# http://stackoverflow.com/questions/1606587/how-to-use-pil-to-resize-and-apply-rotation-exif-information-to-the-file
			if ctype == "image":
				image = pyexiv2.Image(outfilename + extension)
				image.readMetadata()
				# We clean the file and add some information
				image.deleteThumbnail()
				image['Exif.Image.Artist'] = IMAGE_ARTIST_COPYRIGHT
				image['Exif.Image.Copyright'] = IMAGE_ARTIST_COPYRIGHT
				
				im = Image.open(outfilename + extension)
				#im.thumbnail(THUMBSIZE, Image.ANTIALIAS)
				
				# We rotate regarding to the EXIF orientation information
				if 'Exif.Image.Orientation' in image.exifKeys():
					orientation = image['Exif.Image.Orientation']
					if orientation == 1:
						# Nothing
						mirror = im.copy()
					elif orientation == 2:
						# Vertical Mirror
						mirror = im.transpose(Image.FLIP_LEFT_RIGHT)
					elif orientation == 3:
						# Rotation 180°
						mirror = im.transpose(Image.ROTATE_180)
					elif orientation == 4:
						# Horizontal Mirror
						mirror = im.transpose(Image.FLIP_TOP_BOTTOM)
					elif orientation == 5:
						# Horizontal Mirror + Rotation 270°
						mirror = im.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.ROTATE_270)
					elif orientation == 6:
						# Rotation 270°
						mirror = im.transpose(Image.ROTATE_270)
					elif orientation == 7:
						# Vertical Mirror + Rotation 270°
						mirror = im.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
					elif orientation == 8:
						# Rotation 90°
						mirror = im.transpose(Image.ROTATE_90)
					
					# No more Orientation information
					image['Exif.Image.Orientation'] = 1
				else:
					# No EXIF information, the user has to do it
					mirror = im.copy()
				
				mirror.save(outfilename + extension)
				img_grand = pyexiv2.Image(outfilename + extension)
				img_grand.readMetadata()
				image.copyMetadataTo(img_grand)
				img_grand.writeMetadata()
				
				mirror.thumbnail(THUMBSIZE, Image.ANTIALIAS)
				mirror.save(outfilename + "-thumb.png", "PNG")
				img_mini = pyexiv2.Image(outfilename + "-thumb.png")
				img_mini.readMetadata()
				image.copyMetadataTo(img_mini)
				img_mini.writeMetadata()
			
			# store this in our list of binaries
			binaries.append((ctype, uid, extension, filename))
			
			# lodge a tag
			if not ctype in tags:
				tags.append(ctype)
		
		# the text message is almost always the first part and is text
		elif partcounter == 1 and part.get_content_maintype() == "text":
			message = part.get_payload(decode=1)

# add to the tags line from the message
message = "\n".join([x.startswith("#tags") and x + "," + ",".join(tags) or x for x in message.split("\n")])

# write the actual template result
entry = file(entryfile, "w")
t = Template(file=os.path.join(TEMPLATE_DIR, "entry.txt"), searchList=[{
	"subject": subject,
	"message": message,
	"binaries": binaries,
	"TEMPLATE_DIR": TEMPLATE_DIR,
	}])
entry.write(str(t))
entry.close()
#print t
#print entryfile, subject, message, binaries