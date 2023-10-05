from django.shortcuts import render
from .forms import YourForm
from django.conf import settings
import pandas as pd
import csv, os, re
import logging

# Get an instance of the logger
logger = logging.getLogger(__name__)

# should be used dotenv() for variables
books_file = 'BX-Books.csv'
ratings_file = 'BX-Book-Ratings.csv'

# Get the base directory of the Django project
base_dir = settings.BASE_DIR

# Construct the path to the 'files' folder within your app
files_folder_path = os.path.join(base_dir, 'booking', 'files')

 # Process the form data
ratings_file_path = os.path.join(files_folder_path, ratings_file)
books_file_path = os.path.join(files_folder_path, books_file)


def generate_view(request):
    if request.method == 'POST':
        form = YourForm(request.POST)
        if form.is_valid():
            your_field_value = form.cleaned_data['your_field']
            if os.path.exists(ratings_file_path) and os.path.exists(books_file_path):
                ratings = read_df(prepare_input(ratings_file_path))
                books = read_df(prepare_input(books_file_path))
                df = filter_books(ratings, books, your_field_value)

                # Convert DataFrame to a list of dictionaries
                data = df.to_dict(orient='records')  
                return render(request, 'extraction_template.html', {'data': data}) 
            else:
                # Handle the case where one or both files do not exist
                logger.error('Error: One or both files not found. Check file paths')                                   
    else:
        form = YourForm()

    return render(request, 'input_template.html', {'form': form})


def prepare_input(file: str, pattern: str = r'(?<![0-9"]);'):
    """
    Prepare and improve input file, merge all cells into one by rows

    Parameters
    ----------
    file : str
        The Directory of input file
    pattern: str
        The pattern matches a semicolon(;) only if it is not preceded
        by either a digit or a double quote.
    """
    with open(file, 'r+', newline='') as f:
            reader = csv.reader(f)
            writer = csv.writer(f)
            
            # Read the header
            header = next(reader)
            
            # Read and modify the data, including the header
            rows = list(reader)
            
            for i, row in enumerate(rows):
                # Combine non-empty values from each column into a single string
                combined_row = ' '.join([cell for cell in row if cell.strip()])
                first_semicolon_index = combined_row.find(';')
                
                # Ignore the first semicolon and apply the pattern to the rest
                combined_row = combined_row[:first_semicolon_index + 1] + re.sub(pattern, '', combined_row[first_semicolon_index + 1:])
                rows[i] = [combined_row]
            
            # Write the header and modified data back to the file
            f.seek(0) 
            writer.writerow(header)
            writer.writerows(rows) 
            
            # Truncate any remaining data if needed
            f.truncate()
            logging.info(f'{file} is prepared for reading.')

    return file


def read_df(file: str):
    """
    Ratings: Book-Rating dropes zero values
    Books: Drop dublicates, non numeric values shifte to 
        right by columns

    Parameters
    ----------
    file: str
        Directory of the input file
    """
    # Read the CSV file with common settings
    df = read_csv_with_settings(file)

    if 'Ratings' in file:
        # Skip Book-Rating with zero values
        df['Book-Rating'] = pd.to_numeric(df['Book-Rating'], errors='coerce')
        df = df[df['Book-Rating']!=0]
        logger.info(f'{file} is processed, rows: {len(df)}')
    else:
        # Drop duplicates based on ISBN
        df = df.drop_duplicates(subset='ISBN', keep='first')

        # Find rows where 'Year-Of-Publication' is non-numeric
        errors = df[~df['Year-Of-Publication'].str.isnumeric()]

        # Clear in df 'Year-Of-Publication' is non-numeric
        df = df.drop(errors.index)
    
        # Shift data to the right column by column
        for col_index in range(len(errors.columns) - 1, errors.columns.get_loc('Book-Author'), -1):
            errors.iloc[:, col_index] = errors.iloc[:, col_index - 1]

        # Clear the starting - Book-Author column
        errors.iloc[:, errors.columns.get_loc('Book-Author')] = ''
        logger.info(f'Items are shifted successfully, rows: {len(errors)}')
        
        # Merge the shifted DataFrame back into the original DataFrame
        df = pd.concat([df, errors], ignore_index=True)
        logger.info(f'{file} is processed, rows: {len(df)}')

    return df


def read_csv_with_settings(file: str):
    """
    Read csv file with defined settings

    Parameters
    ----------
    file : str
        Directory of the input file
    """
    # Read CSV file with specified settings
    df = pd.read_csv(
        file,
        encoding='cp1251',
        sep=';',
        header=0,
        quoting=3,
        on_bad_lines='skip',
        engine='python',
    )

    # Clean DataFrame
    clean_df(df)

    return df


def clean_df(df):
    """
    Clean DataFrame by replacing quotes and converting ISBN to uppercase

    Parameters
    ----------
    df : DataFrame
        Input DataFrame to be cleaned
    """
    # Replace chars in columns and values
    df.columns = df.columns.str.replace('"', '').str.replace(',', '')
    df.replace('"', '', regex=True, inplace=True)

    # Convert ISBN to uppercase
    df['ISBN'] = df['ISBN'].str.upper()


def filter_books(ratings:pd.DataFrame, books: pd.DataFrame, word:str):
    """
    Filter most 5 recommended books based on input word from 2 dataframes

    Parameters
    ----------
    ratings : DataFrame
        Created DataFrame from Ratings file
    books : DataFrame
        Created DataFrame from Books file
    word : str
        Input word by user for searching
    """

    # Merge two data frames
    dataset = pd.merge(ratings, books, on=['ISBN'])
    # Filter books with word in their titles
    books = dataset[dataset['Book-Title'].str.contains(fr'\b{word}\b', case=False, na=False)]
    # Calculate total ratings for each book
    book_ratings = books.groupby('ISBN')['Book-Rating'].sum().reset_index()
    # Find the most popular book
    top_5_recommended_books = book_ratings.nlargest(5, 'Book-Rating')
    
    # Merge top 5 recommended books with the original 'books' DataFrame
    # to get additional information for presenting web only
    result_df = pd.merge(top_5_recommended_books, books, on=['ISBN'], how='left')
    result_df = result_df.drop_duplicates(subset='ISBN', keep='first')
    logger.info(f'Finally found rows: {len(result_df)}')
    result_df.replace('', pd.NA, inplace=True)
    result_df.columns = result_df.columns.str.replace('-', '_')
    
    return result_df