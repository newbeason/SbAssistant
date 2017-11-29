import re
import sys
import logging
import datetime
import configparser
from logging.handlers import TimedRotatingFileHandler
from decimal import Decimal
from lxml.html import fromstring

from ScrapUtil import download_page, login_page


class CheckinReview:
	def __init__(self, conf_file):
		self.init_conf(conf_file)
		if self.login:
			self.login_shanbay()
		self.ask_for_leave_members = set()
		if self.askForLeave:
			self.ask_for_leave_members = self.scrap_ask_for_leave_members()

	def init_conf(self, conf_file):
		conf = configparser.ConfigParser()
		conf.read(conf_file)
		section = conf['common']

		self.login = conf.getboolean('common', 'login')
		self.loginUrl = section['login_url']
		self.username = section['username']
		self.password = section['password']
		self.baseUrl = section['base_url']
		self.memberManageUrl = section['member_manage_url']
		self.maxPage = int(section['max_page'])
		self.maxDispel = int(section['max_dispel'])
		self.askForLeave = conf.getboolean('common', 'ask_for_leave')
		self.confirm = conf.getboolean('common', 'confirm')
		self.askForLeaveTopicUrl = section['ask_for_leave_topic_url']
		self.dispelUrl = section['dispel_url']
		self.nonLocalTimeMembers  = section['non_local_time_members']
		logging.info('''load config info, login-{}, loginUrl-{},username-{},
			password-{},baseUrl-{},memberManageUrl-{},maxPage-{},maxDispel-{},
			askForLeave-{},askForLeaveTopicUrl-{},dispelUrl-{}'''.format(
			self.login,self.loginUrl,self.username,
			self.password,self.baseUrl,self.memberManageUrl,
			self.maxPage,self.maxDispel,self.askForLeave,
			self.askForLeaveTopicUrl,self.dispelUrl))

	def login_shanbay(self):
		login_params = {
			'username' : self.username,
			'password' : self.password
		}
		headers = {'Referer':'https://www.shanbay.com/accounts/login/'}
		self.session = login_page(self.loginUrl,login_params,headers=headers)

	# 进入用户管理页面,遍历页面处理
	def start_review(self):
		dispel_members = self.fetch_to_dispel_members()
		member_ids = list()
		for member_id in dispel_members.keys():
			member_ids.append(member_id)
		if self.maxDispel < len(member_ids):
			member_ids = member_ids[:self.maxDispel]
		if self.confirm:
			confirm = input('are you sure to dispel members: {}, \input y or n: \
				'.format(member_ids))
			if confirm == 'y':
				self.disple_members(member_ids)
			else:
				logging.info("you input {}, will not dispel".format(confirm))
		else:
			self.disple_members(member_ids)

	def fetch_to_dispel_members(self):
		session = self.session
		group_manage_page_content = download_page(
			self.memberManageUrl, session=session)
		tree = fromstring(group_manage_page_content)
		# print(group_manage_page_content)
		page_links = tree.xpath('//a[contains(@class,"endless_page_link")]/text()')
		last_page_num = int(page_links[-2]) if len(page_links) > 0 else 1
		print(last_page_num)
		dispel_members = dict()
				
		# for page in range(1,int(last_page_num)+1):
		# review recent 16 pages for performance and security
		max_page = int(self.maxPage)
		max_page = last_page_num if max_page > last_page_num else max_page
		logging.info('max_page: {}'.format(max_page))
		for page in range(1,max_page+1):
			page_content = download_page(
				self.memberManageUrl + '?page=' + str(page),session=session)
			dispel_members.update(self.review_on_page(page_content,page))

		#display all dispel members
		logging.info('all of the being dispeled members:')
		logging.info(str(dispel_members))
		return dispel_members

	#处理单个页面数据
	def review_on_page(self,page_html,page_num):
		logging.info('start to review page {}'.format(page_num))
		dispel_members = dict()
		tree = fromstring(page_html)
		member_rows = tree.xpath('//tr[contains(@class,"member")]')
		for member_row in member_rows:
			member_group_id = int(member_row.get('data-id'))
			role = int(member_row.get('role'))
			nickname_a = member_row.find('.//a')
			points_td = member_row.findtext('./td[@class="points"]')
			days_td = member_row.findtext('./td[@class="days"]')
			rate_td = member_row.findtext('./td[@class="rate"]/span')
			checked_spans = member_row.findall('./td[@class="checked"]/span')
			logging.debug('{},{}===={}-{}-{}-{}-{}-{}-{}'.
				format(role,member_group_id,nickname_a.get('href'),
				nickname_a.text,points_td,days_td,rate_td,
				checked_spans[0].text.strip(),checked_spans[1].text.strip()) )
			rate = Decimal(rate_td[:-1])
			member_id = nickname_a.get('href')[14:-1]
			nickname = nickname_a.text

			days = int(days_td)
			# only disple normal member
			if role != 2:
				continue
			# don't dispel members who joined on reivew day.
			if days == 0:
				continue
			#any of last two days checked, will not dispel
			if checked_spans[0].text.strip() == '已打卡' or checked_spans[1].text.strip() == '已打卡':
				continue

			logging.info('start to get member checkin records,{}-{}'.format(member_id,nickname))
			member_checkin_page = download_page(self.baseUrl+nickname_a.get('href'),session=self.session)
			(username,check_list) = self.scrap_recent_check_record_of_member(member_checkin_page)
			# ask for leave in 2 days, will not dispel
			if username in self.ask_for_leave_members:
				continue
			# dispel if rate < 94.50, 
			if rate < 94.50:
				dispel_members[member_group_id] = '{}-{},check rate < {}, rate:{}'.format(member_id,nickname,94.50,rate)
				continue
			
			
			last_check_date = max(check_list)
			logging.debug('last check date: {}'.format(last_check_date))
			today = datetime.date.today()
			review_date = datetime.datetime(today.year,today.month,today.day)
			uncheck_consecutive_days = (review_date - last_check_date).days - 1
			nonLocal_time_member_list = list(self.nonLocalTimeMembers.split(',')) if self.nonLocalTimeMembers else []
			logging.info('nonLocalTimeMembers: {}'.format(self.nonLocalTimeMembers))
			if member_id in nonLocal_time_member_list:
				uncheck_consecutive_days -= 1

			# dispel if consecutive 4 days for any member
			if uncheck_consecutive_days >= 4:
				dispel_members[member_group_id] = '{}-{},uncheck_consecutive_days >= {},uncheck_consecutive_days:{}; rate:{}'.format(member_id,
					nickname,4,uncheck_consecutive_days,rate)
			# dispel if consecutive 2 days uncheck and rate < 97
			elif rate < 97 and uncheck_consecutive_days >= 2:
				dispel_members[member_group_id] = '{}-{},uncheck_consecutive_days >= {},uncheck_consecutive_days:{}; check rate < {}, rate:{}'.format(member_id,
					nickname,2,uncheck_consecutive_days,97,rate)
			# dispel if consecutive 3 days uncheck and rate < 98
			elif rate < 98 and uncheck_consecutive_days >= 3:
				dispel_members[member_group_id] = '{}-{},uncheck_consecutive_days >= {},uncheck_consecutive_days:{}; check rate < {}, rate:{}'.format(member_id,
					nickname,3,uncheck_consecutive_days,98,rate)
			

		logging.info('ended review page {}'.format(page_num))
		logging.info('to dispel member ids:' + str(dispel_members))
		return dispel_members

	def modify_date_format(self,zh_date_str):
		months = list(zip(['十二月','十一月','十月','九月','八月','七月','六月','五月','四月','三月','二月','一月'],range(12,0,-1)))
		for month in months:
			if not zh_date_str.find(month[0]):
				return zh_date_str.replace(month[0],str(month[1]))

	# 解析用户最近10天打卡记录,并按照打卡日期倒序排序
	def scrap_recent_check_record_of_member(self,page_content):
		# page_content = download_page(url,session=self.session)
		tree = fromstring(page_content)
		username_str = tree.xpath('//div[@class="span8"]/div[@class="page-header"]/h2')[0].text
		username = username_str.strip('的日记').strip()
		check_date_strs = tree.xpath('//div[@class="span4" and contains(text(),"月")] ')
		check_list = list()
		for check_date_str in check_date_strs:
			check_date = self.modify_date_format(check_date_str.text.strip())
			check_list.append( datetime.datetime.strptime(check_date,'%m %d, %Y') )
		check_list.sort(reverse=True)
		logging.debug('username:' + username)
		logging.debug('checklist:' + str(check_list))
		
		return (username,check_list)

	# 获取最近指定日期内请假人员的username
	def scrap_ask_for_leave_members(self,days_diff = 2):
		logging.info('start to scrap ask for leave topic')
		page_content = download_page(self.askForLeaveTopicUrl,session=self.session)
		tree = fromstring(page_content)
		# get last page number
		last_page_url = tree.xpath('//a[contains(text(),"最后页")]')[0].get('href')
		logging.debug('last_page_url: ' + last_page_url)
		last_page_num = int(last_page_url[6:])
		ask_for_leave_members = set()
		for page_num in range(last_page_num-1,last_page_num+1):
			post_page_content = download_page( '{}?page={}'.format(self.askForLeaveTopicUrl,page_num), session=self.session)
			ask_for_leave_members.update(self.fetch_members_from_ask_for_leave_page_content(post_page_content))
		
		logging.info('ask for leave members: {}'.format(str(ask_for_leave_members)))
		return ask_for_leave_members
	
	# 获取请假帖子单页数据,返回user_name
	def fetch_members_from_ask_for_leave_page_content(self,page_content,days_diff=2):
		tree = fromstring(page_content)
		post_divs = tree.xpath('//div[contains(@class,"post")]/div[@class="span7"]')
		members = set()
		for post_div in post_divs:
			user_href = post_div.find('.//a[@class="user"]').get('href')
			time_str = post_div.findtext('.//span[@class="time"]')
			if time_str.find('年')>=0 or time_str.find('月')>=0 or time_str.find('周')>=0:
				continue
			matchs = re.findall(r'.*?(\d)\s日.*?',time_str)
			if  len(matchs) > 0 and int(matchs[0]) > days_diff:
				continue
			else:
				members.add(user_href[11:-1])
			
		logging.info('ask for leave members: ' + str(members))
		return members
		
	#dispel members
	def disple_members(self,member_ids):
		data = {
			'action': 'dispel',
		}
		if isinstance(member_ids, (list, tuple)):
			data['ids'] = ','.join(map(str, member_ids))
		else:
			data['ids'] = member_ids
		print(data)
		r = self.session.put(self.dispelUrl, data=data)
		logging.debug('dispel member response: {}'.format(r.text))
		try:
			return r.json()['msg'] == "SUCCESS"
		except Exception as e:
 			logging.exception(e)
		return False
def main():
	time_ratate_handler = TimedRotatingFileHandler('H:/private/python/SbAssistant/log/checkin_review_log.txt','d',1,30)
	stream_handler = logging.StreamHandler(sys.stdout)
	logging.basicConfig(
			# filename='checkin_reviwe_log.txt',
			format = '%(asctime)s %(levelname)s %(filename)s [line:%(lineno)d]: %(message)s',
			level = logging.DEBUG,
			handlers = [stream_handler,time_ratate_handler]
		)
	cr = CheckinReview('H:/private/python/SbAssistant/config/setting.ini')
	cr.start_review()
	
	
if __name__ == '__main__':
	main()
	
	