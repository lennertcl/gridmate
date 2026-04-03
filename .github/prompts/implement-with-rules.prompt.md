# Implement user's request but adhere to the following rules
### General
- Always use snake_casing everywhere
- All data transmission happens in JSON format
- Unless there's a good technical reason, all imports should be at the top of the file, not inside functions or classes 
- Prefer .env and .env.local variables for configuration over constants in the code for development setup related stuff
- ALWAYS run `./run-checks.sh` after making changes and address all reported issues before considering the task complete

### Architecture
- This Python Flask application is a deployed as a Home Assistant addon running as a Docker container. Follow best practices for this scenario. 
- The application is structured as follows:
1. Routes: Flask routes handle all incoming HTTP requests to the backend. Think controllers in an MVC context. Business logic should be kept to a minimum here. 
2. Forms: Flask WTForms are used for all user input that should go to the backend. 
3. Model: All business logic, logically grouped in subpackages and classes. Prefer splitting up into multiple files but keep small and tightly related classes together. 
4. Static: All CSS and JS files.
5. Templates: Frontend jinja2 templates.
6. Data: This addon stores a minumum of data required to function, namely only the configuration. All actual data should come from Home Assistant as this is the main data source for this application. 

### Integrations
The application builds on top of Home Assistant and several integrations. When implementing features, maximally reuse what these integrations already provide and do not reinvent the wheel.
ALWAYS use relevant skills when interacting with these tools: 
- [Home Assistant skill](../skills/home-assistant.md)
- [EMHASS skill](../skills/emhass.md)


### Documentation
- All documentation must go under the docs folder in a markdown file. Exactly 1 documentation file should be present for each feature of the app. 
- ALWAYS check the docs folder for relevant documentation before starting implementation. Read relevant documentation upfront to find all relevant parts of the application to update. 
- ALWAYS update relevant documentation after making changes to make sure documentation and code are in sync. 
- Limit documentation to at most 1 file per front-end page. E.g. 1 file explaining the goals and implementation for the energy costs dashboard, 1 file explaining everything related to configuring your energy contract settings, etc. 
- User guides are included in the application rather than in the docs folder. These must ALWAYS be
updated when implementing new features or changing existing features. User guides are the main source of information for users and should be kept up to date at all times. They can be found in the web/templates/guides folder. 
- Logically structure documentation in subfolders in the docs folder
- All documentation should follow a similar structure:
1. Overview: high-level overview of what this feature achieves
2. Relevant artefacts: Link all files with relevant code for this feature: Templates, Routes, Forms, Models, Services and custom CSS/JS. Do not link generic files used for most features such as e.g. main.css
3. Models: explain the backend models in detail
4. Services: explain the services in detail
5. Forms: explain the forms in detail
6. Routes: explain the routes in detail
7. Frontend: explain the frontend in detail
- Use practical examples where relevant and useful throughout the documentation
- Avoid comments in code! All documentation is written in the docs files. A small, 1 line comment is permitted for complex implementations but this should occur very infrequently. 

### Front-end
- Use Flasks jinja2 html templates for all front-end pages. Make exactly 1 template per page. Import scripts and stylesheets from web/static if needed. 
- Stick to the defined color scheme in main.js and do not use other colors than the defined colors. If another color is needed, define it in main.css. 
- All CSS and JS should be under web/static/css or web/static/js and may NEVER go inside a html template file. The only exception to this rule is for injecting variables from the backend into JS.
- Generic and reusable classes MUST go in main.css.
- All CSS that's only useful for 1 specific page MUST go in a separate file with the same name as the html template, e.g. for energy-dashboard.html make energy-dashboard.css and match the subfolder structure from the templates.
- Logically structure all JS code in separate .js files for separate duties and make the code maximally reusable throughout the project. It should never be necessary to rewrite similar snippets again. 
- NEVER EVER write comments in front-end code files.
- All communication from the front-end to Home Assistant must go through the websocket api using the token. home-assistant-connector.js contains all logic for connecting using the token that can be fetched from the back-end. 
- Avoid complex JS processing that should be done by the backend. JS may only be used for charts, realtime websocket updating pages with HA data, visual effects (limited)
- Prefer Flask WTForms and standard form POST over JavaScript fetch/AJAX for simple form submissions. Only use JS POST logic when there is a clear technical reason (e.g. real-time updates, complex multi-step interactions).
- Use the [frontend-design skill](../skills/frontend-design.md) for all frontend design decisions.