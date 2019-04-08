from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
import time
import os
import pandas as pd 
import requests
import sys
import json

class FbAdLinkFinder():

    def __init__(self, driver, un, pw): 

        self.driver = driver
        self.un = un 
        self.pw = pw
        self.start()       

    def start(self):

        self.login_fb()
        # self.download_all(self.medias)

    def go_to_url(self, media_url):

        self.driver.get(media_url)
    
    def login_fb(self):
    
        # Go to my Fb homepage
        self.go_to_url(r'https://www.facebook.com')
        self.driver.find_element_by_id('email').send_keys(self.un)
        self.driver.find_element_by_id('pass').send_keys(self.pw)
        self.driver.find_element_by_id('loginbutton').click()
        print('Logged into Facebook')

    def body_screenshot(self, ad_id):

        # Take screenshot of whole page
        body = self.driver.find_element_by_tag_name('body')
        body_data = body.screenshot_as_png
        file_loc = r'./output/screenshots/{}_s0.png'.format(ad_id)
        with open(file_loc, 'wb+') as handler:
            handler.write(body_data)

    def get_media_link(self, media_url, html_tag):
    
        # Get links of images & videos from page
        media_tags = self.driver.find_elements_by_tag_name(html_tag)
        media_links = []
        try:
            media_links = [m.get_attribute('src') for m in media_tags]
        except StaleElementReferenceException as e:
            print(e)
            print('At this link {}'.format(media_url))
        except Exception as e:
            print('Unexpected error', e)
            print('At this link {}'.format(media_url))

        return media_links

    def get_all_links(self, medias):

        # Take screenshot of each page + get all img and vid links
        media_dict = {}
        print('\nGetting batch media links')

        for (ad_id, url) in medias:
            self.go_to_url(url)
            self.body_screenshot(ad_id)
            img_urls = self.get_media_link(url, 'img')
            vid_urls = self.get_media_link(url, 'video')
            media_dict[ad_id] = [img_urls, vid_urls]

        return media_dict    
        
class MediaDownloader():

    def __init__(self, media_types):
        self.media_types = media_types
        if set(media_types) - {'img', 'vid'} == set():
            self.okay = True
        else:
            self.okay = False
        
    def __bool__(self):
        return self.okay()
    
    def parse_md(self, md):
        img_urls = []
        vid_urls = []

        for k, [ims, vs] in md.items():
            ims = ims[1:] # don't download my profile photo
            for idx, im in enumerate(ims):
                img_urls.append((k, im, idx))
            for idx, v in enumerate(vs):
                vid_urls.append((k, v, idx))
        return [img_urls, vid_urls]
    
    def download_all(self, media_urls, media_type, root_folder):
        
        # Download all images + videos in media_urls
        if media_type == 'img':
            print('Downloading all images')
            for ad_id, m, idx in media_urls:
                file_name = r'{}{}_image{}.jpg'.format(root_folder, ad_id, idx)
                self.img_dl(m, ad_id, idx, file_name)

        elif media_type == 'vid':
            print('Downloading all videos')
            for ad_id, m, idx in media_urls:
                file_name = r'{}{}_video{}.mp4'.format(root_folder, ad_id, idx)
                self.aria_dl(m, ad_id, idx, file_name)            

    def img_dl(self, img_url, ad_id, img_num, file_name):

        # Download image in link
        img_data = None
        try:
            img_data = requests.get(img_url).content 
        except (ConnectionError) as e:
            print(e)
            print('Img: {}\nLink: {}'.format(ad_id, img_url))
        except Exception as e:
            print('Unexpected error. {}'.format(e))
            print('Img: {}\nLink: {}'.format(ad_id, img_url))

        if img_data != None:
            with open(file_name, 'wb+') as handler:
                handler.write(img_data)
        # print('Finished img download: {}'.format(file_name))

    def aria_dl(self, vid_url, ad_id, vid_num, file_name):

        # Aria2c video downloads
        aria2c_call = r'aria2c "{}" -o {}'.format(vid_url, file_name)
        format_output = r' --show-console-readout=false --console-log-level=warn --summary-interval=0'
        try:
            os.system(aria2c_call + format_output)
        except Exception as e:
            print('Unexpected error. {}'.format(e))
            print('Vid: {}\nLink: {}'.format(ad_id, vid_url))
        # print('Finished vid download: {}'.format(file_name))        


def open_headless_chrome(webdriver_loc):
    
    # Open an instance of Google Chrome
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1200x600')
    options.add_argument('log-level=3') ## supress STOP from Fb
    driver = webdriver.Chrome(chrome_options = options, executable_path=webdriver_loc)

    return driver

def read_fb_api(df_loc, my_vars, row_n=0, row_start=0):
    '''Read Fb API data.

    Args:
        df_loc: A CSV file with containing information on individual ads.
        my_vars: List of two columns names - [unique-ad-id, ad-url]
        row_n: No. of rows from top that will be downloaded
        row_start: Row no. from where to start downloading
    '''
    df = pd.read_csv(df_loc)
    if row_n == 0:
        row_n = df.shape[0]
    my_rows = list(range(row_start, row_n))
    medias = df.loc[my_rows, my_vars]
    medias.ad_id = medias.ad_id.str.replace('\'', '')
    medias = [tuple(x) for x in medias.values]

    return medias

def chunk_list(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]



def main():

    # FB credentials
    with open('./data/fb.pw', 'r') as f:
        fb = f.read().split('\n')
    un = fb[0]
    pw = fb[1]

    batch_size = 100
    # starting_i = 0
    starting_i = 7500

    if len(sys.argv) == 4:
        batch_size = sys.argv[1]
        un = sys.argv[2]
        pw = sys.argv[3]
    elif len(sys.argv) == 2:
        batch_size = int(sys.argv[1])
        

    # Open Google Chrome
    try:
        webdriver_loc = r'./chromedriver_win32/chromedriver.exe'
        driver = open_headless_chrome(webdriver_loc)
    except OSError as e:
        webdriver_loc = r'./chromedriver_linux64/chromedriver'
        driver = open_headless_chrome(webdriver_loc)
    except Exception as e:
        print(e)

    # Parse FB API data
    # df_loc = r'./data/Greg_Martin_for_coders_file1.csv'
    # my_vars = ['snapshot_id', 'ad_url']
    # medias = read_fb_api(df_loc, my_vars, row_n = 100, row_start=starting_i)
    df_loc = r'./data/outside_groups_ads_v4.csv'
    my_vars = ['ad_id', 'ad_snapshot_url']
    medias = read_fb_api(df_loc, my_vars, row_start=starting_i)
    staggered_medias = chunk_list(medias, batch_size)

    # File destinations + File types
    media_types = ['img', 'vid']
    links_root_folder = './output/ad_links/'
    img_root_folder = './output/ad_imgs/'
    vid_root_folder = './output/ad_vids/'
    
    # Login to Fb + Ready to download
    open_fb = FbAdLinkFinder(driver, un, pw)
    ready_to_dl = MediaDownloader(media_types)

    for idx, sm in enumerate(staggered_medias):
        # return media links in a dict
        media_dict = open_fb.get_all_links(sm)
        file_name = r'{}media_dict{}.json'.format(links_root_folder, idx + starting_i/batch_size)
        with open(file_name, 'w+') as f:
            json.dump(media_dict, f, indent=4)

        # Download all imgs and vids to output folder
        [img_urls, vid_urls] = ready_to_dl.parse_md(media_dict)
        ready_to_dl.download_all(img_urls, 'img', img_root_folder)
        ready_to_dl.download_all(vid_urls, 'vid', vid_root_folder)


if __name__ == '__main__':

    main()
