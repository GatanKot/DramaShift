### DramaShift
Finds the most dramatic posts over a time from scored and posts them to rdrama. 

Because of api limitations you 
can only get the last 1000 posts by date, so this also monitors communities to not
miss posts and normalize by time.

For example, if post 1000 was created 10 hours ago, it will recalculate the drama 
score for all posts later than 10 * k where k < 1, hours ago, if they weren't already
recalculated. Then it waits and repeats.

At a fixed time every day, it posts the most dramatic posts from yesterday.

thedonald gets about 2000 posts a day, the rest you can pull the entire month before 
reaching the end (consumeproduct, kotakuinaction2, greatawakening) the rest of 
communities are practically abandoned.

Main Features:

Posts most dramatic n posts to rDrama as a catalogue

Posts most dramatic post to rDrama with controversial comments quoted

Monitor mode will automatically post the best drama from the past [day]

Minor:

Drama ranking algorithm

You can make a cool graph of all posts' drama

Near Planned:

Unit tests 

Account for how controversial the comments are in drama ranking. 

Far Planned:

Add other sites. Stormfront and Breitbart maybe.