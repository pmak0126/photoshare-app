import os
import json
import base64
import io
import numpy as np
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, redirect, session, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import face_recognition
from PIL import Image

VERSION = "v3-facematch"
ALLOWED_USERS = ["pranavcoolstar@gmail.com", "makwanapranav26@gmail.com"]

SPREADSHEET_ID = "1gWWBNp6U1lIEz7RCiCycIqvg