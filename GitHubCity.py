#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This module allow to developers to get all users of GitHub that have a given
city in their profile. For example, if I want getting all users from London,
I will get all users that have London in their profiles (they could live in London or not)

Author: Israel Blancas @iblancasa
Original idea: https://github.com/JJ/github-city-rankings
License:

The MIT License (MIT)
    Copyright (c) 2015 Israel Blancas @iblancasa (http://iblancasa.com/)

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software
    and associated documentation files (the “Software”), to deal in the Software without
    restriction, including without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom
    the Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all copies or
    substantial portions of the Software.

    THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
    INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
    PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
    FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
    IN THE SOFTWARE.

"""

import urllib.request
import threading
import concurrent.futures
import datetime
import calendar
import time
from multiprocessing import Queue
import json
from urllib.error import HTTPError
from dateutil.relativedelta import relativedelta
import os
import sys
import logging
import coloredlogs
sys.path.append(os.getcwd())
from GitHubUser import *



class GitHubCity:
    """Manager of a GithubCity.

    Attributes:
        _city (str): Name of the city (private).
        _names (set): Name of all users in a city (private)
        _githubID (str): ID of your GitHub application.
        _githubSecret (str): secretGH of your GitHub application.
        _dataUsers (List[GitHubUser]): the list of GitHub users.
    """

    def __init__(self, city, githubID, githubSecret, excludedJSON=None, debug=False):
        """Constructor of the class.

        Note:
            To get your ID and secret, you will need to create an application in
            https://github.com/settings/applications/new .

        Args:
            city (str): Name of the city you want to search about.
            githubID (str): ID of your GitHub application.
            githubSecret (str): Secret of your GitHub application.

        Returns:
            a new instance of GithubCity class

        """

        if city==None:
            raise Exception("City is not defined")

        self._city = city

        if githubID==None:
            raise Exception("No GitHub ID inserted")
        self._githubID = githubID

        if githubSecret==None:
            raise Exception("No GitHub Secret inserted")
        self._githubSecret = githubSecret

        self._names = Queue()
        self._myusers = set()
        self._excluded = set()

        self._dataUsers = []

        self._threads = set()

        if excludedJSON:
            for e in excludedJSON:
                self._excluded.add(e["name"])

        self._logger = logging.getLogger("GitHubCity")

        if debug:
            coloredlogs.install(level='DEBUG')

        self._fin = False


    def _addUser(self, new_user):
        """Add new users to the list (private).

        Note:
            This method is private.

        Args:
            new_users (List[dict]): a list of users to include in our users's list.

        Returns:
            Difference between the total of new_users and users repeat. In another words
            the method returns the number of users added in this time to the users list.

        """
        if not new_user in self._myusers and not new_user in self._excluded:
            myNewUser = GitHubUser(new_user)
            myNewUser.getData()
            self._myusers.add(new_user)
            self._dataUsers.append(myNewUser)
            self._logger.debug("NEW USER "+new_user+" "+str(len(self._dataUsers)+1)+" "+\
            threading.current_thread().name)



    def _readAPI(self, url):
        """Read a petition to the GitHub API (private).

        Note:
            This method is private.
            If max number of request is reached, method will stop 1 min.

        Args:
            url (str): URL to query.

        Returns:
            The response of the API -a dictionary with these fields-:
                * total_count (int): number of total users that match with the search
                * incomplete_results (bool): https://developer.github.com/v3/search/#timeouts-and-incomplete-results
                * items (List[dict]): a list with the users that match with the search

        """

        code = 0
        hdr = {'User-Agent': 'curl/7.43.0 (x86_64-ubuntu) libcurl/7.43.0 OpenSSL/1.0.1k zlib/1.2.8 gh-rankings-grx',
               'Accept': 'application/vnd.github.v3.text-match+json'
               }
        while code != 200:
            req = urllib.request.Request(url, headers=hdr)
            self._logger.debug("Getting data from "+url)
            try:
                response = urllib.request.urlopen(req)
                code = response.code
            except urllib.error.URLError as e:
                reset = int(e.getheader("X-RateLimit-Reset"))
                now_sec = calendar.timegm(datetime.datetime.utcnow().utctimetuple())
                self._logger.warning("Limit of API. Wait: "+str(reset - now_sec)+" secs")
                time.sleep(reset - now_sec)
                code = e.code

        data = json.loads(response.read().decode('utf-8'))
        response.close()
        return data

    def _getURL(self, page=1, start_date=None, final_date=None,order="asc"):
        """Get the API's URL to query to get data about users (private).

        Note:
            This method is private.

        Args:
            page (int): number of the page.
            start_date (datetime.date): start date of the range to search users.
            final_date (datetime.date): final date of the range to search users.

        Returns:
            The URL (str) to query.

        """
        if not start_date or not final_date:
            url = "https://api.github.com/search/users?client_id=" + self._githubID + "&client_secret=" + self._githubSecret + \
                "&order=desc&q=sort:joined+type:user+location:" + self._city + \
                "&sort=joined&order=asc&per_page=100&page=" + str(page)
        else:
            url = "https://api.github.com/search/users?client_id=" + self._githubID + "&client_secret=" + self._githubSecret + \
                "&order=desc&q=sort:joined+type:user+location:" + self._city + \
                "+created:" + start_date.strftime("%Y-%m-%d") +\
                ".." + final_date.strftime("%Y-%m-%d") +\
                "&sort=joined&order="+order+"&per_page=100&page=" + str(page)

        return url

    def _processUsers(self):
        #coloredlogs.install(level='DEBUG')
        while not self._fin or not self._names.empty():
            new_user = self._names.get()
            if new_user:
                self._addUser(new_user)
                new_user = None



    def _launchThreads(self):
        i = 0
        while i<40:
            i+=1
            newThr = threading.Thread(target=self._processUsers)
            newThr.setDaemon(True)
            self._threads.add(newThr)
            newThr.start()

    def _getPeriodUsers(self, start_date, final_date):
        """Get all the users given a period (private).

        Note:
            This method is private.
            User's names are added to the private _name attribute.

        Args:
            start_date (datetime.date): start date of the range to search users.
            final_date (datetime.date): final date of the range to search users.

        """
        self._logger.info("Getting users from "+start_date.strftime("%Y-%m-%d")+" to "+\
        final_date.strftime("%Y-%m-%d"))

        self._launchThreads()

        url = self._getURL(1, start_date, final_date)
        data = self._readAPI(url)

        total_pages = 10000
        page = 1

        while total_pages>=page:
            url = self._getURL(page, start_date, final_date)
            data = self._readAPI(url)
            for u in data['items']:
                self._names.put(u["login"])
            total_count = data["total_count"]
            total_pages = int(total_count / 100) + 1
            page += 1

        self._fin = True

        for t in self._threads:
            t.join()

        self._fin = False



    def _readAndAdd(self,page):
        url = self._getURL(page)
        data = self._readAPI(url)
        self._addUsers(data["items"])


    def _getSmallCityUsers(self, totalUsers, newGetUsers):
        totalPages = totalUsers/100+1
        page = 2
        thr = set()

        newThr = threading.Thread(target=self._addUsers, args=(newGetUsers,))
        newThr.setDaemon(True)
        thr.add(newThr)
        newThr.start()

        while page<=totalPages:
            newThr = threading.Thread(target=self._readAndAdd, args=(page,))
            newThr.setDaemon(True)
            thr.add(newThr)
            newThr.start()
            page+=1

        self._logger.debug(str(len(thr))+" threads to calculate city")
        self._logger.info("Waiting all threads")

        for t in thr:
            t.join()



    def getCityUsers(self):
        """Get all the users from the city.
        """
        comprobation = self._readAPI(self._getURL())
        if comprobation["total_count"]>=1000: #Big City
            self._logger.info("Big city")
            for i in self._intervals:
                self._getPeriodUsers(i[0], i[1])

        else:
            self._logger.info("Small city")
            self._getSmallCityUsers(comprobation["total_count"],comprobation["items"])


    def _validInterval(self, start, finish):
        data = self._readAPI(self._getURL(1,start,finish))
        if data["total_count"]>=1000:
            middle = start + (finish - start)/2
            self._validInterval(start,middle)
            self._validInterval(middle,finish)
        else:
            self._intervals.add((start,finish))
            self._logger.debug("Valid interval: "+start.strftime("%Y-%m-%d")+" to "+\
            finish.strftime("%Y-%m-%d"))




    def calculateBestIntervals(self):
        self._intervals = None
        comprobation = self._readAPI(self._getURL())

        if comprobation["total_count"]>=1000: #Big City
            self._intervals = set()
            self._bigCity = True
            self._validInterval(datetime.date(2008, 1, 1), datetime.datetime.now().date())
            self._logger.info("Total number of intervals: "+ str(len(self._intervals)))
        else:
            self._bigCity = False


    def getTotalUsers(self):
        """Get the number of calculated users
        Returns:
            Number (int) of calculated users
        """
        if len(self._names) == 0:
            return -1
        else:
            return len(self._names)
