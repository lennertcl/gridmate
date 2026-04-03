---
name: emhass
description: "Create energy management optimizations building on the EMHASS (Energy Management for Home Assistant) application. Use this skill when the user asks to build anything related to energy management or optimization. It points to documentation files to be read for better understanding of how to connect with EMHASS. 
---

This skill guides creation of energy management or optimization tools 
on top of an existing Home Assistant layer which already has an EMHASS
addon integrated. It serves the purpose to explain EMHASS documentation. 

The user will provide the guidelines related to what should be built, 
you MUST always fetch and check relevant documentation before starting implementation to 
grasp how aspects of EMHASS work. 


## Guidelines
When building on top of EMHASS, maximally reuse what EMHASS already
provides. You do not want to reinvent the wheel. 

The essence of what you are building is an application that serves the following tasks: 
- Provides clean, rich and user-friendly dashboard and configuration for EMHASS
- Simplifies the EMHASS interface for non-technical users and makes energy 
management accessible to everyone
- Combines the strengths of Home Assistant, EMHASS and other integrations
into a single application that is powerfull yet elegantly simple to use 

You are NOT: 
- Making the optimization model. EMHASS has a good model. Use it. 
- Making a frontend for the user to pass every bit of configuration that EMHASS exposes. 
Users can pass this data directly in EMHASS if they want to change it. Keep it minimal yet 
functional and easy for non-technical users who want a good energy management experience.  

When writing code that interacts with EMHASS, ALWAYS CHECK DOCS FIRST from below pages. 

## EMHASS documentation
- EMHASS configuration parameters: https://emhass.readthedocs.io/en/latest/config.html
- EMHASS core concepts: https://emhass.readthedocs.io/en/latest/main_core_concepts.html
- Passing data to EMHASS: https://emhass.readthedocs.io/en/latest/passing_data.html
- Forecast data: https://emhass.readthedocs.io/en/latest/forecasts.html
- Technical background and linear programming formulation: https://emhass.readthedocs.io/en/latest/advanced_math_model.html
- EMHASS api: https://raw.githubusercontent.com/davidusb-geek/emhass/refs/heads/master/src/emhass/web_server.py