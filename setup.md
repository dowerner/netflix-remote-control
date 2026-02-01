# Idea
The goal is to create a project that acts as a sort of Netflix remote. The idea is that a device such as a Raspberry Pi 5 can run this project which then launches a browser in kiosk mode and also runs an API that allows clients like a TV remote app to send navigation, play, pause, stop, etc. commands.

# Requirements
- Needs to work on Linux based systems (x64, ARM 64)
- Should be implemented in Python
- Should provide a way to store auth information for the kiosk browser. On initial launch would navigate to the netflix login page and then potentially store the cookie (look at @NFAuthenticationKey.py)
- Control API should be simple to start with

Generate a plan to implement this application.