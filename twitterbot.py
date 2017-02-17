import twitter
import datetime
import time
import threading
import sys

followKeyWords = ['#follow', 'follow', 'following'] # list of keywords that twitter uses as 'follow'
retweetKeyWords = ['#rt', '#retweet', 'retweet', 'rt'] # list of keywords they say to 'retweet' 
mixedKeyWords = ['rt+follow', 'rt/follow'] # keywords when they say it together

tweetsInQueue = [] # list containing api.Status's to be retweeted
alreadyTweeted = [] # list of already tweeted retweets; to prevent duplicate retweeting
lock = threading.RLock() # lock shared by threads to protected shared data

searchWords = ['#giveaway', 'giveaway'] # list of words to perform a Twitter search on
dailyTweetLimit = 2400 # number of tweet/retweets per day
hourlyTweetLimit = 25
maxFollowers = 1500 # max number of followers for account

myScreenName = None
api = None

currentRetweets = 0 # keep track of number retweets sent out each day
currentFollowers = 0 # keep track of the number of following each day
searchTime = datetime.datetime.now()
tweetTime = datetime.datetime.now()

logEnabled = True # change this to false to disable any logging to file
def debugLog(msg):
    """
    Opens logFile.txt and appends msg to the file.
    Will only open file if logEnabled.
    """
    if logEnabled == True:
        with open('logFile.txt', 'a') as file:
            file.write(msg)

def loadApi():
    """
    Loads the user's twitter keys from file into the 
    api and initializes it.
    """
    global api
    global myScreenName
    keys = {}

    with open('api_keys.cfg', 'r') as file: # open file containing Twitter api keys
        for line in file:
            tokens = line.strip().split('=') # parse each line in file and create dict of keys
            keys[tokens[0]] = tokens[1]

    api = twitter.Api(consumer_key = keys['consumer_key'], consumer_secret = keys['consumer_secret'],\
                    access_token_key = keys['access_token_key'], access_token_secret = keys['access_token_secret'])
    myScreenName = keys['screen_name'] # set your screen name that is used on Twitter

def SearchGiveaways(num):
    """
    Performs a Twitter search on each string in searchWords list.
    Returns a list of twitter.Status objects.
    """
    allResults = list() # list of all found results
    for word in searchWords:
        try:
            searches = api.GetSearch(term=word, geocode=None, since_id=None, max_id=None, until=None, count=num, lang=None, locale=None, result_type='recent', include_entities=None)
            allResults.extend(searches)
        except Exception as e:
            debugLog(str(e))
            print(str(e))
    return allResults
    
def FilterResults(results):
    """
    Filter list of twitter.Status objects to find only tweets with the properites:
        - follow and retweet keywords found in status
    returns filtered list of twitter.Status objects
    """
    validTweets = []
    for tweet in results:
        follow = False
        retweet = False
        text = tweet.text.encode('utf-8').lower()
        i = text.find(':')
        if i >= 0:
            i += 1
            text = text[i:]
        text = text.replace('&amp;', ' and ') # replace ampersands with the word and ('RT&amp;Follow' => 'RT and Folllow')
        
        # find any 'follow' keywords
        for keyword in followKeyWords:
            if keyword in text:
                follow = True
                break
        # find any 'retweet' keywords
        for keyword in retweetKeyWords:
            if keyword in text:
                retweet = True
                break
        # find any mixed keywords
        for keyword in mixedKeyWords:
            if keyword in text:
                retweet = True
                follow = True
                break
        if follow == True and retweet == True:
            validTweets.append(tweet)
    
    return validTweets

def PostTweets():
    """
    Retweet queued tweets to Twitter and follow users.
    Retweets upto the hourlyTweetLimit count.
    Will remove oldest following if past max limit of allowed followers. 
    """
    global tweetsInQueue
    global alreadyTweeted
    global currentRetweets
    global currentFollowers

    if currentRetweets >= dailyTweetLimit:
        print('Exceeded retweet limit ({}) for the day.'.format(dailyTweetLimit))
        return # no more tweeting for the day

    if currentFollowers >= maxFollowers: # remove followers if past max
        print('Over {} Followers. Removing Followers First ...'.format(maxFollowers))
        RemoveOldestFollowers()

    limit = min(hourlyTweetLimit, len(tweetsInQueue)-1) # get tweet limit for this hour: minimum of hourlyTweet or amount in queue

    success = 0
    for i in range(0, limit):
        tID = tweetsInQueue[i].id # tweet id
        status = tweetsInQueue[i].text.encode('utf-8') # tweet text
        
        if status in alreadyTweeted == True:
            print ('{} of {}: Tweet already posted ...'.format(i, limit))
            continue
        
        start = status.find('@') + 1
        end = status.find(':')
        user = status[start:end] # get original posters screenname (placed in front of the status text)

        lock.acquire()
        try:
            print('Retweeting {} of {} ...'.format(i, limit))

            api.CreateFriendship(screen_name=user) # Attempt to post retweet and follow person
            currentFollowers += 1
            
            api.PostRetweet(tID)
            currentRetweets += 1
            time.sleep(90) # post a retweet every 2 minutes.
            success += 1
        except Exception as e:
            debugLog('   Error:' + str(e))
            print ('   Error:' + str(e))
        
        alreadyTweeted.append(status)
        lock.release()

    with lock:
        tweetsInQueue = tweetsInQueue[i:] # create new list with posted retweets removed

    print('Retweeted {} successfully ...'.format(success))
    
def RemoveOldestFollowers(remove_count=25):
    """
    Removes specified amount of people you are following.
    Default value is remove_count=25.
    """
    global currentFollowers
    foes = api.GetFriendIDs(user_id=None, screen_name=myScreenName, cursor=-1, stringify_ids=False, count=None)
    
    for i in range(0, remove_count):
        userID = foes.pop() # get ID of following
        api.DestroyFriendship(userID) # unfollow them
        currentFollowers -= 1
        time.sleep(3)
    
def printTweets():
    """
    Print each tweet that is in queue to be tweeted.
    """
    for tweet in tweetsInQueue:
        content = tweet.text.encode('utf-8')
        print (content.replace('&amp;', ' and ').lower())
        print ('--------------------------------------------')

def printStats():
    """
    Print some information about tweets that have happened
    on the current day and when next tweet/search times are.
    """
    print('----------------------------------------')
    print('|                Info                  |')
    print('----------------------------------------')
    print('+ tweetsInQueue : ' + str(len(tweetsInQueue)))
    print('+ alreadyTweeted: ' + str(len(alreadyTweeted)))
    print('+ Following     : ' + str(currentFollowers))
    print('+ Tweets today  : ' + str(currentRetweets))
    print('----------------------------------------')
    print('+ Next search   : ' + searchTime.strftime('%I:%M %p'))
    print('+ Next retweet  : ' + tweetTime.strftime('%I:%M %p'))
    print('----------------------------------------')

def startNewDay():
    """
    Resets stats for a new day.
    Truncate the list of tweeted status' to prevent a large list.
    Sync number of following with Twitter.
    """
    global currentRetweets
    global currentFollowers
    global alreadyTweeted
    
    print('New Day ...')   
    currentRetweets = 0 # zero out numer of tweets for today

    with lock:
        alreadyTweeted.reverse() # reverse list to remove oldest tweets from list
        newLen = len(alreadyTweeted) / 2
        alreadyTweeted = alreadyTweeted[0:newLen] # truncate tweeted list to half its size

    try:
        me = api.GetUser(user_id=None, screen_name=myScreenName, include_entities=False)
        with lock:
            currentFollowers = me.friends_count # get number of following from Twitter
    except Exception as e:
        debugLog(str(e))
        print(str(e))

    threading.Timer(86400, startNewDay).start()

def doRetweet():
    """
    Function executed by a threading.Timer.
    Will post retweets if any are in queue.
    Starts another threading.Timer to be called the next hour.
    """
    global tweetTime
    global tweetsInQueue
    
    if len(tweetsInQueue) == 0:
        print('Nothing to retweet for now ...')
    else:
        print('Retweeting ...')
        try:
            PostTweets()
        except Exception as e:
            print('Failed to retweet, error: ', str(e))

    tweetTime = datetime.datetime.now() + datetime.timedelta(hours=1)
    print('Retweets finished @ ' + str(datetime.datetime.now()))
    print('Next retweet @ ' + str(tweetTime))
    threading.Timer(3600, doRetweet).start()

def doSearch(count=40):
    """
    Function executed by a threading.Timer.
    Will perform a search on Twitter.
    Starts another threading.Timer to be called the next hour.
    """   
    global searchTime
    global tweetsInQueue
        
    if len(tweetsInQueue) > hourlyTweetLimit:
        print('Currently have {} tweets in queue. NOT performing a search this hour ...'.format(len(tweetsInQueue)))
    else:
        try:
            print('Searching ...')
            results = SearchGiveaways(count) # get collection of search results
            with lock:
                tweetsInQueue.extend(FilterResults(results)) # filter out any inelligible tweets and place in queue
        except Exception as e:
            print('Failed to search, error: ', str(e))

    searchTime = datetime.datetime.now() + datetime.timedelta(hours=1) # next search will be in 1 hour
    print('Search finished @ ' + str(datetime.datetime.now()))
    print('Next search @ ' + str(searchTime))
    threading.Timer(3600, doSearch).start()

if __name__ == "__main__":

    loadApi() # load api settings from file and init api

    startNewDay() # set stats for new day
    doSearch() # do a search after initilization and will repeat every hour

    threading.Timer(15, doRetweet).start() # do retweets in 15 seconds to give search time to finish

    while True: # loop on main loop to accept any user input
        try:
            c = raw_input('Enter Command[p|q|pt|s]: ')
            if c == 'p': # print table of stats about the current day
                printStats()
            if c == 'q': # quit the program. will wait if a thread is sleeping
                for t in threading.enumerate():
                    print(str(t))
                    if type(t) is threading._Timer:
                        t.cancel()
                print('goodbye ...')
                sys.exit(0)
            if c == 'pt': # print all tweet status' in queue
                printTweets()
            if c == 's': # perform a search on twitter
                for t in threading.enumerate()[1:]:
                    if t.function.func_name == 'doSearch':
                        t.cancel() # stop timer before doing a search if running already
                        break
                doSearch(count=20)
        except Exception as e:
            debugLog(str(e))
            print(str(e))
        
    
