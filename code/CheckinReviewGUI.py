from tkinter import *
from tkinter import ttk, filedialog, messagebox
from logging.handlers import TimedRotatingFileHandler
import logging
import sys
import requests
from lxml.html import fromstring

from CheckinReview import CheckinReview




shared_data = {}

def fetch_members():
    shared_data['images'] = []
    _images.set(()) #initialized as an empty tuple
    try:
        member_list = ([(member_id,reason) for member_id,reason in cr.fetch_to_dispel_members().items()])
    except requests.exceptions.RequestException as rex:
        _sb(str(rex))
    else:
        if member_list:
            member_reasons = tuple([member[1] for member in member_list ])
            shared_data['members'] = member_list
            _images.set(member_reasons)
            _sb('members found: {}'.format(len(member_reasons)))
        else:
            _sb('members did not found')
    
        # config['images'] = images

def dispel():
    images_index = _img_listbox.curselection()
    if images_index:
        members = shared_data['members']
        selected_members = [members[index][0] for index in images_index]
        logging.info('selected members: {}'.format(str(selected_members)))

        result = messagebox.askyesno(
                message='Are you sure you want to dispel these members?',
                icon='question',
                title='Dispel')
        logging.debug('Are you sure you want to dispel these members? {}'.format(result))
        if result:
            cr.disple_members(selected_members)
    else:
        _alert('No selected members.')

def _sb(msg):
    _status_msg.set(msg)

def _alert(msg):
    messagebox.showinfo(message=msg)

if __name__ == '__main__':
    time_ratate_handler = TimedRotatingFileHandler('H:/private/python/SbAssistant/log/checkin_review_log.txt','d',1,30)
    stream_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
            # filename='checkin_reviwe_log.txt',
            format = '%(asctime)s %(levelname)s %(filename)s [line:%(lineno)d]: %(message)s',
            level = logging.DEBUG,
            handlers = [stream_handler,time_ratate_handler]
        )
    cr = CheckinReview('H:/private/python/SbAssistant/config/setting.ini')

    _root = Tk()
    _root.title('SbAssistant')

    _mainframe = ttk.Frame(_root, padding='5 5 5 5')
    _mainframe.grid(row=0, column=0, sticky=(E,W,N,S))

   
    _img_frame = ttk.LabelFrame(
        _mainframe, text='Content', padding='9 0 0 0')
    _img_frame.grid(row=1, column=0, sticky=(N,S,E,W))

    _images = StringVar()
    _img_listbox = Listbox(
        _img_frame, listvariable=_images, height=20, width=80, selectmode="extended")
    _img_listbox.grid(row=0, column=0, sticky=(E,W), pady=5)
    _scrollbar = ttk.Scrollbar(
        _img_frame, orient=VERTICAL, command=_img_listbox.yview)
    _scrollbar.grid(row=0, column=1, sticky=(S,N), pady=6)
    _img_listbox.configure(yscrollcommand= _scrollbar.set)

    
    _fetch_btn = ttk.Button(
        _mainframe,
        text='Fetch Members',
        command=fetch_members)
    _fetch_btn.grid(row=2, column=0, sticky=W, padx=5)
    _scrape_btn = ttk.Button(
        _mainframe, text='Scrape!', command=dispel)
    _scrape_btn.grid(row=2, column=1, sticky=E, pady=5)

    _status_frame = ttk.Frame(
        _root, relief='sunken', padding='2 2 2 2')
    _status_frame.grid(row=1,column=0,sticky=(E,W,S))
    _status_msg = StringVar()
    _status_msg.set('')
    _status = ttk.Label(
        _status_frame, textvariable=_status_msg, anchor=W)
    _status.grid(row=0, column=0, sticky=(E,W))

    _root.mainloop()
