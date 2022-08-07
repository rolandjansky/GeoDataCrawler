 # Case study for real estate firm
This code is based on an assessment I did where I had the following...

## Mission
“Die Post” provides their address-data free accessible to use. Unfortunately, the coordinates
of each address are not provided in the free version. We provide you a WebAPI which you
can use to geo-locate all these addresses. With these enriched addresses, we want you to
create a GeoJSON formatted file. The properties of each point should be: street, street
number, zip, locality, latitude (enriched from our API) and longitude (enriched from our
API).

## What I did
1. Read the description of the assessment, got an overview of all related files
2. Tried to understand what is needed to get to the expected result (GeoJSON)
      - Looked at the Post_Adressdaten20170425.csv file, skimmed through the description --> Okay, this is a relational DB stored as csv. --> Data can be easily and efficiently transformed in a Python app. Still took around 20 minutes to understand all the details, pick the right fields, etc.
      - lat/lon information needs to be retrieved from REST API --> easy enough, quite familiar with doing this in Python apps. We do however need to query the API in an inefficient way (e.g. no bulk requests are supported by the server). This will be IO limited and the server will likely not be happy about the 1M+ requests. I haven't worked with such a task previously.
      - Looked up what GeoJSON is (compared to JSON), which did only take couple of minutes as it's super simple. Then also looked up what library exists to easily write this out without any custom code.
3. Next I validated that the transformed data I got from the csv file is valid by comparing it with other public sources that list existing addresses for a given street name and such
4. I spent around 60-90 minutes googling what appropriate solutions are for the "API scraping" problem are and what libraries exist. The code for this was then largely copy & paste from very similar problems other people already solved.
      - My main uncertainty here is how efficient my solution is.
      - I implemented a semaphore as there seems to be a limitation on the number of concurrent open sockets just from my Windows machine
      - The REST API however anyway seems to limit the number of request more stringent than this limit. I've introduced a limiter which I eventually set to not run more than 80 requests per second. Above that the server eventually rejects the connection for some time. For this case I've introduced another safe guard that slows down the request rate by letting a task that encounters this issue sleep for some seconds. Sadly I wasn't able to figure out how the server really enforces rate limiting. At first I'm able to bombard it with request for several minutes, so it doesn't seem to be a simple req/second limit. Or maybe it doesn't enforce rate limits at all.. Maybe I just overloaded it.
5. Since time was quickly approaching the 4 hours, I then wrote the method for writing out the data to a GeoJSON file so that I do have some output

## What I did not manage to do
1. I usually do test-driven-development. Here I really was not sure what methods I'll be ending up with and what there input/outputs will be, and hence I postponed writing tests and eventually ran out of time to do so. This one hurts me the most for not having done it. Good tests also largely replace any other doc strings or comment needed in the implementation, hence this is also missing.
2. Also there wasn't time for several other needed additions like using a proper retry policy, more efficient processing of the input data (better using the CPU resources)
3. I also didn't have time to containerize this app or something. Also it has very little dependencies and is easy to run, hence this is not strictly necessary.
4. Since I could only query the server reliably at 80 requests per second, I did not run a job which actually queries the server for all addresses - as this would take around 6 hours at this rate

## Files
- [Python script to transform and enrich Swiss postal service address data](akwrd.py)
- [Test for all methods in akwrd.py which I wish wI could have implemented](test_akwrd.py)
- [Example of 10k addresses enriched with the latitude and longitude](Post_Adressdaten20170425.geojson) 
