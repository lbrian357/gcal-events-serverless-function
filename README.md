Lambda function that services serverless api [OPTION & PUT] endpoints that captures an event attendees name, email and newsletter preference.

Integrates with a google calendar (v3), google sheets (v4) and google drive (v3) to add the attendee to a google cal event and save their contact info along with their newsletter preference in a google sheet unique to event.

Zipping python lambda for deploy:
1. cd into /package
2. run: zip -r ../my-deployment-package.zip .
3. cd out of /package (into root dir where lambda_function.py is)
4. run: zip my-deployment-package.zip lambda_function.py
