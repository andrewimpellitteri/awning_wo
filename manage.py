#!/usr/bin/env python3
"""
Management script for Awning Management System
"""

import os
import sys
from flask import Flask
from flask.cli import with_appcontext
import click
from werkzeug.security import generate_password_hash

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models.user import User
from utils.csv_handler import CSVHandler

@click.group()
def cli():
    """Awning Management System CLI"""
    pass

@cli.command()
@with_appcontext
def init_db():
    """Initialize the database"""
    click.echo('Initializing database...')
    db.create_all()
    click.echo('Database initialized successfully!')

@cli.command()
@with_appcontext
def drop_db():
    """Drop all database tables"""
    if click.confirm('This will delete all data. Are you sure?'):
        db.drop_all()
        click.echo('Database tables dropped.')

@cli.command()
@click.option('--username', prompt=True)
@click.option('--email', prompt=True)
@click.option('--password', prompt=True, hide_input=True)
@with_appcontext
def create_user(username, email, password):
    """Create a new user"""
    if User.query.filter_by(username=username).first():
        click.echo(f'User {username} already exists.')
        return
    
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password)
    )
    
    db.session.add(user)
    db.session.commit()
    
    click.echo(f'User {username} created successfully!')

@cli.command()
@with_appcontext
def import_csv():
    """Import data from CSV files"""
    click.echo('Importing CSV data...')
    
    csv_handler = CSVHandler()
    success, message = csv_handler.import_all_csvs()
    
    if success:
        click.echo(f'✅ {message}')
    else:
        click.echo(f'❌ {message}')

@cli.command()
@with_appcontext
def sample_data():
    """Create sample data for testing"""
    click.echo('Creating sample data...')
    
    # Create sample user if doesn't exist
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123')
        )
        db.session.add(admin_user)
    
    # Create sample reference data
    from models.reference import Material, Color, Condition
    
    materials = ['Canvas', 'Vinyl', 'Acrylic', 'Polyester']
    for material_name in materials:
        if not Material.query.filter_by(name=material_name).first():
            db.session.add(Material(name=material_name))
    
    colors = ['White', 'Green', 'Blue', 'Red', 'Yellow', 'Black']
    for color_name in colors:
        if not Color.query.filter_by(name=color_name).first():
            db.session.add(Color(name=color_name))
    
    conditions = ['New', 'Good', 'Fair', 'Poor', 'Damaged']
    for condition_name in conditions:
        if not Condition.query.filter_by(name=condition_name).first():
            db.session.add(Condition(name=condition_name))
    
    # Create sample customer
    from models.customer import Customer
    if not Customer.query.filter_by(name='Sample Customer').first():
        customer = Customer(
            name='Sample Customer',
            contact='John Doe',
            address='123 Main St',
            city='Anytown',
            state='NY',
            zip_code='12345',
            home_phone='(555) 123-4567',
            email_address='customer@example.com'
        )
        db.session.add(customer)
    
    db.session.commit()
    click.echo('Sample data created successfully!')

if __name__ == '__main__':
    with app.app_context():
        cli()
