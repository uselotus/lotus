#!/bin/bash 
cd backend 
python manage.py generate_schema
cd .. 
cd gen 
npm run update-types
cd ..

