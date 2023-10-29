---
name: Feature request
about: Suggest an idea for this project
---

## Is your feature request related to a problem? Please describe.
A clear and concise description of what the problem is. Ex. I'm always frustrated when [...]

## Describe the solution you'd like
<!-- A clear and concise description of what you want to happen. -->

## Describe alternatives you've considered
<!-- A clear and concise description of any alternative solutions or features you've considered. -->

## Vacuum
<!-- List your vacuum's model here. If this applies to all vacuum models, leave this blank -->

## Additional context
<!-- Add any other context or screenshots about the feature request here. -->

## Mqtt request
<!-- If you are looking for a feature that was introduced with a specific vacuum, chances are the reason we have not implemented it is because we need the mqtt request - and we cannot figure it out as we don't have the vacuum. Look here(https://github.com/humbertogontijo/python-roborock/blob/main/roborock/typing.py) to see what commands we have. If we don't have one that corresponds with the feature you are looking for, chances are, we need your (or another users' help)

If you feel as if you are technically able to do this, please do, if not, just say here that you don't feel comfortable doing this.

You can either create the connection manually using: https://medium.com/geekculture/capture-iphone-ios-http-traffic-using-wireshark-4af01a4313e6

Or get it made automatically using Airtools 2

Using a Mac, download wireshark and download Airtools 2. Then using airtools 2, select "Capture iPhone Packet Trace". Once wireshark gets launched by airtools, enter the following: "ip.addr == (Your robots ip here (no parenthesis)) and data.data and tcp" hit enter.

Make sure your phone is on the same network as your vacuum, then open the roborock app, and do the task that you are looking to get added to the integration. Make sure items are appearing in wireshark. If they are, then once you have done all the tasks you want added, hit hte stop button on the top of wireshark, then File-> save as -> pcapng. 

You can just upload the file and we can decode it for you.
-->