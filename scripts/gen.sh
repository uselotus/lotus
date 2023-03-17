#!/bin/bash 
cd gen 
npm run update-types
cd ..
cd backend 
python manage.py generate_schema
cd .. 
