# Setup & Installation

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Git
- pip and virtualenv

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/andrewimpellitteri/awning_wo.git
cd awning_wo
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Database

Create a PostgreSQL database:

```bash
createdb clean_repair
```

### 5. Configure Environment Variables

Create a `.env` file:

```bash
FLASK_ENV=development
FLASK_DEBUG=true
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://postgres:password@localhost:5432/clean_repair
```

### 6. Run Migrations

```bash
./alembic_db.sh prod upgrade head
```

### 7. Run the Application

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

## Running Tests

```bash
pytest
pytest --cov=. --cov-report=html  # With coverage
```

## Next Steps

- Read the [Project Structure](project-structure.md) guide
- Review the [Database Schema](database-schema.md)
- Check out [Testing](testing.md) to write tests
