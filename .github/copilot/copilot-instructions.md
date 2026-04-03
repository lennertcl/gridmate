# GitHub Copilot Instructions

**Priority Guidelines**

When generating code for this repository:

1. **Version Compatibility**: Respect the exact dependency versions observed in the repository. The project pins `Flask==3.1.2` in [requirements.txt](requirements.txt#L3). Do not suggest APIs or behaviors that only exist in versions newer than this.
2. **Context Files**: Prioritize patterns and guidance placed under `.github/copilot` (this file) and any other repository files.
3. **Codebase Patterns**: When specific guidance is not present in `.github/copilot`, mimic the coding style and organization found in the repository files.
4. **Architectural Consistency**: Keep the project structure monolithic and minimal: 
- web
  - main: contains all Flask and routing code
  - model: contains all Python model code (data models, connectors, ...)
  - static: contains all css and js code
  - templates: contains all html templates
5. **Code Quality Focus**: Prefer maintainability, security-conscious defaults, and testability consistent with the repository's current patterns.
6. **Context awareness**: Check the [README file](README.md) for the project context and goals. Always keep the application context in mind when adding or updating features. Check the [docs folder](docs/) for additional context about the application domain.

**Technology**
- **Python3**: 
  - Flask==3.1.2 framework
- **Vanilla JS**
  - Use plain JS, CSS and HTML for front-end code in combination with Jinja2 for dynamic content
  - Use (Flask) best practices for HTML, CSS and JS
  - Use Chart.js for stunning charts
  - Use open source icon packs for a modern UI
  - Keep the UI visually interesting yet minimalistic and professional
  - Use placeholders in case an image should be present (under web/static/images/abc/xyz). Add a descriptive alt that can be used to identify or generate a fitting image. 
- **Home Assistant**
  - The application is deployed as a Home Assistant Plugin running in Docker
  - Use the JS websockets API for real-time updating dashboards from the front-end
  - Use the REST or websockets API for requesting other data from the Flask back-end

**Code Quality Standards (Observed-driven)**

**Maintainability**
- **Naming**: Follow the simple, descriptive names seen in `app.py` (for example, `app`, `hello_world`).
- **Simplicity**: Keep functions small and focused, matching the repository's minimal single-responsibility handlers.
- **Reuse**: 
    * Restrict custom CSS and JS in HTML templates to small snippets only. For larger code, use web/static/css/main.css and web/static/css/main.js or create separate files under web/static/css/ or web/static/js/ and link them in the HTML templates.
    * Reuse existing CSS classes for elements like buttons, cards, etc. Do NOT create new classes for this unless a new type of component is needed. 
    * Only use colors from the existing color scheme as defined in main.css. 

**Documentation Requirements**

- Keep inline comments and docstrings consistent with the repository's minimal style. 
- Avoid verbose API docs unless the repository contains examples to emulate. 
- Update documentation in the `docs/` folder as needed to reflect new features or changes.

**Generation Rules (Hard constraints)**

- Do not introduce language or framework features that are not verifiably supported by repository files or pinned dependencies.
- Any new dependency must be added to `requirements.txt` with an explicit version pin.
- Preserve the container entrypoint approach: `run.sh` executes `python3 /app/app.py`; do not replace the launcher without updating `run.sh` and `Dockerfile` in the same change.
