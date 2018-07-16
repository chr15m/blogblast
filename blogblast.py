#!/usr/bin/python
# vim: set fileencoding=utf-8 :

ENTRIES_DIR = "./entries"
ATTACHMENTS_DIR = "./attachments"
TEMPLATE_DIR = "./templates"
ATTACHMENTS_URL = "/attachments"
ALLOWED_FROM_EMAILS = ["john@smith.com"]
IMAGE_ARTIST_COPYRIGHT = "John Smith"
THUMBSIZE = (400, 800)
MAKETHUMB = True
LOGFILE = "blogblast.log"

### config over ###

import email.Parser
from uuid import uuid4
import htmlentitydefs
import sys
import os
import re
from datetime import datetime

from Cheetah.Template import Template

import Image
import pyexiv2

# set the umask so our files have the right permissions
os.umask(022)

# change to the directory where this script lives
os.chdir(os.path.realpath(os.path.dirname(__file__)))

# read local_config.py for config updates
if os.path.isfile("settings_local.py"):
	from settings_local import *

# open a logfile
log = file(LOGFILE, "w+")
sys.stderr = log

def logit(msg):
	log.write(msg + "\n")

# log the starting time

logit("%s - Starting" % datetime.now().strftime("%Y-%m-%d %H:%M"))

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
			extension = os.path.splitext(filename)[1] or "." + part.get_content_subtype()
			# generate a new output filename
			uid = str(uuid4())[:8]
			outfilename = os.path.join(ATTACHMENTS_DIR, uid + "-" + filename.replace(extension, ""))
			# write this file out
			outfile = open(outfilename + extension, "wb")
			outfile.write(part.get_payload(decode=1))
			outfile.close()
			
			logit("Attachment %d: %s %s" % (partcounter, filename, (outfilename + extension)))
			# if it's an image, rotate it to the correct orientation
			# and make a thumbnail
			# http://stackoverflow.com/questions/1606587/how-to-use-pil-to-resize-and-apply-rotation-exif-information-to-the-file
			if ctype == "image" and extension.lower() in [".jpg", ".jpeg", ".png", ".bmp"] and MAKETHUMB:
				image = pyexiv2.ImageMetadata(outfilename + extension)
				image.read()
				# We clean the file and add some information
				image.exif_thumbnail.erase()
				image['Exif.Image.Artist'] = IMAGE_ARTIST_COPYRIGHT
				image['Exif.Image.Copyright'] = IMAGE_ARTIST_COPYRIGHT
				
				im = Image.open(outfilename + extension)
				#im.thumbnail(THUMBSIZE, Image.ANTIALIAS)
				
				# We rotate regarding to the EXIF orientation information
				if 'Exif.Image.Orientation' in image.exif_keys:
					orientation = image['Exif.Image.Orientation'].value
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
					try:
						image['Exif.Image.Orientation'] = pyexiv2.XmpTag('Exif.Image.Orientation', 1)
					except KeyError:
						pass
				else:
					# No EXIF information, the user has to do it
					mirror = im.copy()
				
				mirror.save(outfilename + extension)
				if extension.lower() in [".jpg", ".jpeg"]:
					img_grand = pyexiv2.ImageMetadata(outfilename + extension)
					img_grand.read()
					#try:
						# copy the metadata
					#	for k in image.exif_keys:
					#		img_grand[k] = image[k]
					#except TypeError:
					#	logit("Oops, metadata error!")
					image.copy(img_grad)
					img_grand.write()
				
				mirror.thumbnail(THUMBSIZE, Image.ANTIALIAS)
				mirror.save(outfilename + "-thumb.png", "PNG")
			
			# store this in our list of binaries
			binaries.append((ctype, uid, extension, filename))
			
			# lodge a tag
			if not ctype in tags:
				tags.append(ctype)
		
		# the text message is almost always the first part and is text
		elif partcounter == 1 and part.get_content_maintype() == "text":
			message = part.get_payload(decode=1)
else:
	logit("Bad from address:" + msg['From'])
	sys.exit("From address " + msg['From'] + " is not allowed")

logit("Done with attachments")

# add to the tags line from the message
message = "\n".join([x.startswith("#tags") and x + "," + ",".join(tags) or x for x in message.split("\n")])

newmessage = ""
tagline = ""
for l in message.split("\n"):
	if l.startswith("#tags "):
		tagline = l
	else:
		newmessage += l + "\n"

if tagline:
	newmessage += tagline + "," + ",".join(tags)
else:
	newmessage += "#tags " + ",".join(tags)

message = newmessage

logit("Done with tags")

# write the actual template result
entry = file(entryfile, "w")
t = Template(file=os.path.join(TEMPLATE_DIR, "entry.txt"), searchList=[{
	"subject": subject,
	"message": message,
	"binaries": binaries,
	"TEMPLATE_DIR": TEMPLATE_DIR,
        "MAKETHUMB": MAKETHUMB,
	}])
entry.write(str(t))
entry.close()

# done with the logfile
log.close()

#print t
#print entryfile, subject, message, binaries

logit(str(entryfile))
logit(str(subject))
logit(str(message))
logit(str(binaries))
logit("Done")
logit("---")
