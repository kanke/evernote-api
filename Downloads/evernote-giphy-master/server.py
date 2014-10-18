from flask import Flask, render_template, request, session, redirect, url_for
import urlparse
import urllib
import requests

from evernote.api.client import EvernoteClient
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.type.ttypes as Types
import evernote.edam.notestore.ttypes as NoteStoreTypes
import evernote.edam.notestore.NoteStore as NoteStore
from evernote.edam.notestore.ttypes import NotesMetadataResultSpec


import binascii
import hashlib

#dev_token = "put your dev token here"
#client = EvernoteClient(token=dev_token)
#userStore = client.get_user_store()
#user = userStore.getUser()
#print user.username

giphy_api_key="dc6zaTOxFJmzC" #public beta key
evernote_auth_token = "S=s1:U=8fb37:E=1507bff7930:C=149244e4a58:P=1cd:A=en-devtoken:V=2:H=421beaffc2c2df6b41d3ddc54964866a"
EN_URL="https://sandbox.evernote.com"


app=Flask(__name__)

@app.route("/", methods=['POST','GET'])
def main():
	""" GET: gets random gif from giphy and displays it along with the option to see another gif and to
	save the gif to their evernote account"""
	if request.method == "GET":
		#get random gif from giphy api
		response=requests.get("http://api.giphy.com/v1/gifs/random?api_key="+giphy_api_key).json()
		if not response:
			return "error with connection to giphy"

		#get random image url and id from giphy api response
		giphy_url=response['data']['image_url']
		giphy_id=response['data']['id']

		#get tags and pass them to the page because the giphy api only show tags for random images
		giphy_tags=''
		for tag in response['data']['tags']:
			giphy_tags+=tag+', '
		giphy_tags=giphy_tags[:-2]

		return render_template("index.html", giphy_url=giphy_url, giphy_id=giphy_id, giphy_tags=giphy_tags)

	"""POST: shows confomation of evernote gif save and presents option
	to return to main page or see the note in evernote"""
	if request.method == 'POST':
		if request.form['giphy_id'] and request.form['giphy_tags']:
			giphy_id=request.form['giphy_id']
			giphy_tags=request.form['giphy_tags']
			response=requests.get("http://api.giphy.com/v1/gifs/"+giphy_id+"?api_key="+giphy_api_key).json()
			giphy_url=response['data']['images']['original']['url']

			client = EvernoteClient(token=evernote_auth_token, sandbox=True)
			user_store = client.get_user_store()
			note_store = client.get_note_store()
			notebooks = note_store.listNotebooks()


			#check if giphy notebook exists
			for notebook in notebooks:
				if notebook.name=="Giphy":
					giphyNotebookGuid=notebook.guid
					break
			#if not create it
			try:
				giphyNotebookGuid
			except NameError:
				notebook=Types.Notebook()
				notebook.name="Giphy"
				notebook=note_store.createNotebook(notebook)
				giphyNotebookGuid=notebook.guid

			#create note title with user name + giphy id for unique identifier
			note_title=response['data']['username']+"-"+response['data']['id']

			#check to see if note exists already
			notebook_filter=NoteStoreTypes.NoteFilter()
			notebook_filter.guid=giphyNotebookGuid
			result_spec = NotesMetadataResultSpec(includeTitle=True)
			noteList    = note_store.findNotesMetadata(evernote_auth_token, notebook_filter,0 , 40000, result_spec)

			for note in noteList.notes:
				if note.title==note_title:
					shardId=user_store.getUser(evernote_auth_token).shardId
					shareKey=note_store.shareNote(evernote_auth_token, note.guid)
					evernote_url="%s/shard/%s/sh/%s/%s" % (EN_URL,shardId,note.guid,shareKey)
					return render_template("already_there.html", giphy_url=giphy_url, evernote_url=evernote_url)


			#get image
			image= requests.get(giphy_url, stream=True).content
			md5 = hashlib.md5()
			md5.update(image)
			gif_hash = md5.digest()

			data = Types.Data()
			data.size = len(image)
			data.bodyHash = gif_hash
			data.body = image

			resource = Types.Resource()
			resource.mime = 'image/gif'
			resource.data = data

			hash_hex = binascii.hexlify(gif_hash)


			note = Types.Note()
			note.notebookGuid=giphyNotebookGuid #create note for our Giphy notebook

			note.title=note_title #name based on Giphy username and id
			note.content = '<?xml version="1.0" encoding="UTF-8"?>'
			note.content += '<!DOCTYPE en-note SYSTEM ' \
			    '"http://xml.evernote.com/pub/enml2.dtd">'
			note.content += '<en-note><br/>'
			note.content += '<en-media type="image/gif" hash="' + hash_hex + '"/>'
			note.content += '</en-note>'

						#add tags to the note
			enTagList=note_store.listTags()
			enTagListNames= [tag.name for tag in enTagList]
			giphyTagList=giphy_tags.split(", ")

			if not note.tagGuids:
				note.tagGuids=[]

			for giphyTag in giphyTagList:
				if giphyTag in enTagListNames:
					for tag in enTagList:
						if tag.name == giphyTag:
							note.tagGuids.append(tag.guid)
				else:
					tag=Types.Tag()
					tag.name=str(giphyTag)
					tag=note_store.createTag(tag)

					note.tagGuids.append(tag.guid)


			note.resources = [resource] # Now, add the new Resource to the note's list of resources

			note=note_store.createNote(note) # create the note

			user=user_store.getUser(evernote_auth_token)
			shardId=user.shardId
			shareKey=note_store.shareNote(evernote_auth_token, note.guid)
			evernote_url="%s/shard/%s/sh/%s/%s" % (EN_URL,shardId,note.guid,shareKey)
			return render_template("saved.html", giphy_url=giphy_url, evernote_url=evernote_url)
		else:
			return "error finding the gif"

	else:
		return "server error"




if __name__=="__main__":
	app.run(debug=True)
