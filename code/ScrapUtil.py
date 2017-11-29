import requests
import time

# download a page 
def download_page(url,retries=2,timeout=10,session=None):
	print("downloading page:" + url)
	try:
		if session:
			r = session.get(url,timeout=timeout)
		else:
			r = requests.get(url,timeout=timeout)
		status_code = r.status_code
		if status_code == requests.codes.ok:
			return r.text
		elif status_code >= 500 and retries > 0 :
			return download_page(url,retries-1,timeout)
		else:
			return None
	except requests.exceptions.RequestException as e:
		print(str(e))
		if retries > 0:
			time.sleep(5 * (3-retries))
			return download_page(url,retries-1,timeout)


#download a file using stream
def download_file_using_get(url,filename):
	try:
		response = requests.get(url,stream=True)
		if response.status_code == requests.codes.ok:
			with open(filename,'wb') as fh:
				for chunk in response.iter_content(1024):
					fh.write(chunk)
			return True
	except requests.exceptions.RequestException as e:
		print(str(e))
	return False;

def download_file_using_post(url,data,filename):
	try:
		response = requests.post(url,data=data,stream=True)
		if response.status_code == requests.codes.ok:
			with open(filename,'wb') as fh:
				for chunk in response.iter_content(1024):
					fh.write(chunk)
			return True
	except requests.exceptions.RequestException as e:
		print(str(e))
	return False;


## login to page, return Session if success, return None if failure.
def login_page(url,params,headers={}):
	session = requests.Session()

	if not headers.get('User-Agent'):
		headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:49.0) Gecko/20100101 Firefox/49.0'
	try:
		r = session.put(url,data=params,headers=headers)
	except requests.exceptions.RequestException as e:
		print(str(e))
		return None
	else:
		print("login response:", r.status_code, ' - ', r.text)
		if r.ok:
			return session
	
	return None