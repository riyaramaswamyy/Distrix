import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional

def get_distributor_name(file_name: str) -> str:
    """
    Extract distributor name from file name.
    
    Args:
        file_name: Name of the file
        
    Returns:
        Distributor name
    """
    # Get just the filename without path
    file_name = os.path.basename(file_name)
    
    # Remove temporary file prefix with regex (handles various tmp formats)
    file_name = re.sub(r'^tmp[a-zA-Z0-9_]*', '', file_name)
    
    # Remove file extension
    distributor_name = os.path.splitext(file_name)[0]
    
    # If empty, use the file extension as a fallback
    if not distributor_name:
        ext = os.path.splitext(file_name)[1]
        distributor_name = f"Distributor-{ext[1:]}" if ext else "Unknown-Distributor"
    
    # Check if we have an Excel sheet name embedded
    sheet_match = re.search(r'(.+) from (.+)', distributor_name)
    if sheet_match:
        # Use sheet name as distributor if available
        sheet_name = sheet_match.group(1).strip()
        if sheet_name:
            distributor_name = sheet_name
    
    # Clean up any remaining special characters
    distributor_name = re.sub(r'[^a-zA-Z0-9 \-_]', '', distributor_name).strip()
    
    # Use a default name if too short or empty
    if len(distributor_name) < 3:
        distributor_name = f"Distributor-{distributor_name or 'Unknown'}"
        
    return distributor_name

def parse_distributor_files(file_paths):
    """
    Parse distributor report files with a specific focus on correctly identifying:
    - Customer/retailer names
    - Product names (not just numeric IDs)
    - Quantities 
    
    Args:
        file_paths: List of temporary file paths
        
    Returns:
        Pandas DataFrame with standardized data
    """
    print("Beginning distributor file parsing with completely revised approach")
    all_data = []
    
    for file_path in file_paths:
        try:
            file_name = os.path.basename(file_path)
            print(f"Processing file: {file_name}")
            
            # Determine file type by extension
            if file_path.lower().endswith('.csv'):
                # Read CSV file - try multiple encodings if needed
                try:
                    df = pd.read_csv(file_path)
                except Exception as e:
                    try:
                        print(f"Trying alternative encoding for {file_name}: {str(e)}")
                        df = pd.read_csv(file_path, encoding='latin1')
                    except Exception as e2:
                        print(f"Failed to read CSV file {file_name}: {str(e2)}")
                        continue
                
                sheet_name = 'CSV'
            else:
                # Handle Excel files
                try:
                    # Get all sheet names
                    excel = pd.ExcelFile(file_path)
                    sheet_names = excel.sheet_names
                    
                    # Just use the first sheet for simplicity
                    if not sheet_names:
                        print(f"No sheets found in Excel file {file_name}")
                        continue
                        
                    sheet_name = sheet_names[0]
                    print(f"Using sheet: {sheet_name} from {file_name}")
                    
                    # Read the Excel file
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                except Exception as e:
                    print(f"Failed to read Excel file {file_name}: {str(e)}")
                    continue
            
            # Skip empty dataframes
            if df.empty:
                print(f"Empty dataframe from {file_name}")
                continue
                
            # Print column names for debugging
            print(f"Columns in {file_name}: {list(df.columns)}")
            
            # APPROACH 1: Look for a header row with "Customer Name" or "Retailer Name"
            # Many distributor reports have headers within the data
            header_row_idx = find_header_row(df)
            
            if header_row_idx is not None:
                print(f"Found header row at index {header_row_idx}")
                data_extract = process_file_with_header(df, header_row_idx, file_name, sheet_name)
                if not data_extract.empty:
                    all_data.append(data_extract)
                    continue
            
            # APPROACH 2: Try special handling for specific file formats
            # Check if it's a "By Customer By SKU" format
            if "BY CUSTOMER BY SKU" in sheet_name or any("customer" in str(c).lower() and "sku" in str(c).lower() for c in df.columns):
                print("Processing as Customer-by-SKU format")
                data_extract = process_customer_by_sku(df, file_name, sheet_name)
                if not data_extract.empty:
                    all_data.append(data_extract)
                    continue
            
            # APPROACH 3: Try to detect products with * in any column (most reliable for product names)
            print("Looking for product descriptions with * markers")
            data_extract = extract_asterisk_products(df, file_name, sheet_name)
            if not data_extract.empty:
                # If this worked, prioritize this data as it likely has the most accurate product names
                print("Successfully extracted product names with * markers - using these as primary data")
                all_data.append(data_extract)
                continue
                
            # APPROACH 4: Fall back to the original basic approach
            print("Using basic extraction approach")
            data_extract = extract_basic(df, file_name, sheet_name)
            if not data_extract.empty:
                all_data.append(data_extract)
                continue
                
            print(f"No valid data could be extracted from {file_name} with any method")
                
        except Exception as e:
            print(f"Error processing file {file_path}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            continue
    
    # Combine all the data we extracted
    if not all_data:
        print("No data was successfully extracted from any files")
        return pd.DataFrame()
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Add quarter information
    current_month = datetime.now().month
    current_year = datetime.now().year
    current_quarter = ((current_month - 1) // 3) + 1
    quarter = f'Q{current_quarter} {current_year}'
    
    combined_df['Month'] = current_month
    combined_df['Year'] = current_year
    combined_df['Quarter'] = quarter
    
    print(f"Final combined data shape: {combined_df.shape}")
    print("First few rows of combined data:")
    print(combined_df.head(10))
    
    return combined_df

def find_header_row(df: pd.DataFrame) -> Optional[int]:
    """
    Find the row containing column headers like 'Customer Name'
    
    Args:
        df: DataFrame to search through
        
    Returns:
        Index of header row if found, None otherwise
    """
    # Check the first 20 rows for header patterns
    for i in range(min(20, len(df))):
        row_values = [str(val).lower().strip() for val in df.iloc[i].values if pd.notna(val)]
        row_text = ' '.join(row_values)
        
        # Check for common header patterns
        if (('customer' in row_text and 'name' in row_text) or 
            ('retailer' in row_text and 'name' in row_text) or
            ('product' in row_text and any(x in row_text for x in ['name', 'description', 'sku', 'item']))):
            return i
    
    return None

def process_file_with_header(df: pd.DataFrame, header_row_idx: int, file_name: str, sheet_name: str) -> pd.DataFrame:
    """
    Process file with a clear header row
    
    Args:
        df: Original dataframe
        header_row_idx: Index of the header row
        file_name: Source file name
        sheet_name: Sheet name
        
    Returns:
        DataFrame with extracted customer & product data
    """
    print(f"Processing with header row: {list(df.iloc[header_row_idx])}")
    
    # Use the header row as column names and skip to actual data
    headers = df.iloc[header_row_idx].tolist()
    data = df.iloc[header_row_idx+1:].copy().reset_index(drop=True)
    
    # Find indices of customer/product columns by header values
    customer_idx = None
    product_idx = None
    qty_idx = None
    city_idx = None
    state_idx = None
    
    for i, header in enumerate(headers):
        if pd.isna(header):
            continue
            
        header_lower = str(header).lower()
        
        if 'customer' in header_lower and 'name' in header_lower:
            customer_idx = i
        elif 'retailer' in header_lower and 'name' in header_lower:
            customer_idx = i
        elif any(term in header_lower for term in ['product', 'description', 'item']):
            product_idx = i
        elif 'quantity' in header_lower or 'qty' in header_lower:
            qty_idx = i
        elif ('city' in header_lower) or ('ship' in header_lower and 'city' in header_lower):
            city_idx = i
        elif ('state' in header_lower) or ('ship' in header_lower and 'state' in header_lower):
            state_idx = i
    
    if customer_idx is None and product_idx is None:
        print("Could not identify customer or product columns in header row")
        return pd.DataFrame()
    
    # Process the rows of data
    rows = []
    for i, row in data.iterrows():
        # Skip rows that are empty or just separators
        values = [str(v).strip() for v in row if pd.notna(v)]
        if not values or all(v in ['', '-', '--', '---', '----'] for v in values):
            continue
        
        # Extract customer name if column was found
        customer = 'Unknown'
        if customer_idx is not None and customer_idx < len(row):
            if pd.notna(row.iloc[customer_idx]):
                customer = str(row.iloc[customer_idx]).strip()
                # Skip if it looks like a header repeat or total line
                if customer.lower() in ['customer name', 'retailer name', 'total', 'grand total', '']:
                    continue
        
        # Extract product name if column was found
        product = 'Unknown Product'
        if product_idx is not None and product_idx < len(row):
            if pd.notna(row.iloc[product_idx]):
                product = str(row.iloc[product_idx]).strip()
                # Skip if it looks like a header repeat
                if product.lower() in ['product', 'description', 'item', 'total', '']:
                    continue
        
        # Extract quantity if column was found
        quantity = 1
        if qty_idx is not None and qty_idx < len(row):
            if pd.notna(row.iloc[qty_idx]):
                try:
                    qty_val = float(str(row.iloc[qty_idx]).replace(',', ''))
                    if qty_val > 0:
                        quantity = int(qty_val)
                except:
                    pass
        
        # Skip rows where we don't have good data
        if customer == 'Unknown' or product == 'Unknown Product':
            continue
            
        # Create row data
        row_data = {
            'Customer Name': customer,
            'Product': product,
            'Quantity': quantity,
            'Source File': file_name,
            'Distributor': get_distributor_name(file_name),
            'Sheet Name': sheet_name
        }
        
        # Add city information if available
        if city_idx is not None and city_idx < len(row):
            if pd.notna(row.iloc[city_idx]):
                city = str(row.iloc[city_idx]).strip()
                if city and city.lower() not in ['city', 'ship city', 'n/a', '-']:
                    row_data['City'] = city
        
        # Add state information if available
        if state_idx is not None and state_idx < len(row):
            if pd.notna(row.iloc[state_idx]):
                state = str(row.iloc[state_idx]).strip()
                if state and state.lower() not in ['state', 'ship state', 'n/a', '-']:
                    row_data['State'] = state
                    
        rows.append(row_data)
    
    if rows:
        print(f"Extracted {len(rows)} rows using header-based approach")
        return pd.DataFrame(rows)
        
    return pd.DataFrame()

def process_customer_by_sku(df: pd.DataFrame, file_name: str, sheet_name: str) -> pd.DataFrame:
    """
    Process BY CUSTOMER BY SKU format files
    
    Args:
        df: Original dataframe
        file_name: Source file name
        sheet_name: Sheet name
        
    Returns:
        DataFrame with extracted data
    """
    # These files typically have product descriptions with * markers
    # We need to find the customer column and product columns
    
    # First, find any row that contains "Customer Name" text
    customer_row_idx = None
    for i in range(min(15, len(df))):
        row_str = ' '.join([str(v).lower() for v in df.iloc[i] if pd.notna(v)])
        if 'customer' in row_str and 'name' in row_str:
            customer_row_idx = i
            break
    
    if customer_row_idx is None:
        print("Could not find Customer Name row in BY CUSTOMER BY SKU format")
        return pd.DataFrame()
    
    # Get the actual data rows (after the header)
    data_df = df.iloc[customer_row_idx+1:].copy().reset_index(drop=True)
    
    # Find customer column and location columns
    customer_col_idx = None
    city_col_idx = None
    state_col_idx = None
    
    # Search for our column headers
    for i in range(len(df.columns)):
        if pd.notna(df.iloc[customer_row_idx, i]):
            val = str(df.iloc[customer_row_idx, i]).lower()
            
            if 'customer' in val and 'name' in val:
                customer_col_idx = i
                print(f"Found Customer Name column at index {i}")
            elif 'ship' in val and 'city' in val:
                city_col_idx = i
                print(f"Found Ship City column at index {i}")
            elif 'city' in val:
                city_col_idx = i
                print(f"Found City column at index {i}")
            elif 'ship' in val and 'state' in val:
                state_col_idx = i 
                print(f"Found Ship State column at index {i}")
            elif 'state' in val:
                state_col_idx = i
                print(f"Found State column at index {i}")
    
    if customer_col_idx is None:
        print("Could not determine Customer Name column in BY CUSTOMER BY SKU format")
        return pd.DataFrame()
        
    # Check each row for products with * marker
    rows = []
    
    for i, row in data_df.iterrows():
        # Skip empty rows
        if row.isna().all():
            continue
            
        # Get customer name
        if customer_col_idx >= len(row) or pd.isna(row.iloc[customer_col_idx]):
            continue
            
        customer = str(row.iloc[customer_col_idx]).strip()
        
        # Skip if it looks like a header, total, or just numbers
        if (customer.lower() in ['customer name', 'total', 'grand total', ''] or
            customer.replace('.', '').replace('-', '').isdigit()):
            continue
            
        # Look for products in all other columns
        found_products = False
        
        for j, val in enumerate(row):
            if j == customer_col_idx or pd.isna(val):
                continue
                
            val_str = str(val).strip()
            
            # Check if this looks like a product with * marker
            if '*' in val_str and len(val_str) > 5:
                # Create row data
                row_data = {
                    'Customer Name': customer,
                    'Product': val_str,
                    'Quantity': 1,  # Default quantity
                    'Source File': file_name,
                    'Distributor': get_distributor_name(file_name),
                    'Sheet Name': sheet_name
                }
                
                # Add city information if available
                if city_col_idx is not None and city_col_idx < len(row):
                    if pd.notna(row.iloc[city_col_idx]):
                        city = str(row.iloc[city_col_idx]).strip()
                        if city and city.lower() not in ['city', 'ship city', 'n/a', '-']:
                            row_data['City'] = city
                            print(f"Found city for {customer}: {city}")
                
                # Add state information if available
                if state_col_idx is not None and state_col_idx < len(row):
                    if pd.notna(row.iloc[state_col_idx]):
                        state = str(row.iloc[state_col_idx]).strip()
                        if state and state.lower() not in ['state', 'ship state', 'n/a', '-']:
                            row_data['State'] = state
                            print(f"Found state for {customer}: {state}")
                
                rows.append(row_data)
                found_products = True
    
    if rows:
        print(f"Extracted {len(rows)} rows using BY CUSTOMER BY SKU approach")
        return pd.DataFrame(rows)
        
    return pd.DataFrame()

def extract_asterisk_products(df: pd.DataFrame, file_name: str, sheet_name: str) -> pd.DataFrame:
    """
    Extract products marked with asterisks from any column
    
    Args:
        df: Original dataframe
        file_name: Source file name
        sheet_name: Sheet name
        
    Returns:
        DataFrame with extracted data
    """
    # Look through all the data for cells containing * patterns
    # which are indicative of product descriptions
    
    # This approach doesn't rely on specific column headers
    product_cells = []
    
    # Track which rows have customers so we can match them
    customer_by_row = {}
    city_by_row = {}
    state_by_row = {}
    
    # Try to identify city and state columns
    city_col_idx = None
    state_col_idx = None
    
    # First check if we have city/state headers
    for i in range(min(10, len(df))):
        for j in range(len(df.columns)):
            if pd.notna(df.iloc[i, j]):
                val = str(df.iloc[i, j]).lower()
                if ('city' in val) or ('ship' in val and 'city' in val):
                    city_col_idx = j
                elif ('state' in val) or ('ship' in val and 'state' in val):
                    state_col_idx = j
    
    # First, try to find customer names, cities, and states in each row
    for i, row in df.iterrows():
        for j, val in enumerate(row):
            if pd.isna(val):
                continue
                
            val_str = str(val).strip()
            
            # Check if this might be a customer name
            # (not too short, not numbers, not common headers/footers)
            if (len(val_str) > 3 and
                not val_str.replace('.', '').replace('-', '').isdigit() and
                not any(x in val_str.lower() for x in ['total', '---', 'customer', 'product', 'sum', 'qty'])):
                
                # Check if this column had "Customer" or "Retailer" in row 0-5
                is_likely_customer = False
                for k in range(min(5, i)):
                    if j < len(df.iloc[k]) and pd.notna(df.iloc[k, j]):
                        header_val = str(df.iloc[k, j]).lower()
                        if 'customer' in header_val or 'retailer' in header_val:
                            is_likely_customer = True
                            break
                
                if is_likely_customer:
                    customer_by_row[i] = val_str
                    
                    # If we have city and state columns, also capture this info
                    if city_col_idx is not None and city_col_idx < len(row) and pd.notna(row.iloc[city_col_idx]):
                        city = str(row.iloc[city_col_idx]).strip()
                        if city and city.lower() not in ['city', 'ship city', 'n/a', '-']:
                            city_by_row[i] = city
                            
                    if state_col_idx is not None and state_col_idx < len(row) and pd.notna(row.iloc[state_col_idx]):
                        state = str(row.iloc[state_col_idx]).strip()
                        if state and state.lower() not in ['state', 'ship state', 'n/a', '-']:
                            state_by_row[i] = state
                            
                    break
    
    # Now find products with asterisks
    rows = []
    
    for i, row in df.iterrows():
        for j, val in enumerate(row):
            if pd.isna(val):
                continue
                
            val_str = str(val).strip()
            
            # Check if this looks like a product with * marker
            if '*' in val_str and len(val_str) > 5:
                # Try to find a customer for this row
                customer = customer_by_row.get(i, 'Unknown')
                
                # If we don't have a customer, look for one in nearby rows
                if customer == 'Unknown':
                    # Check up to 3 rows before and after
                    for offset in range(1, 4):
                        if i-offset in customer_by_row:
                            customer = customer_by_row[i-offset]
                            break
                        if i+offset in customer_by_row:
                            customer = customer_by_row[i+offset]
                            break
                
                # Only add if we have a valid customer
                if customer != 'Unknown':
                    # Create row data dictionary with base information
                    row_data = {
                        'Customer Name': customer,
                        'Product': val_str,
                        'Quantity': 1,  # Default quantity
                        'Source File': file_name,
                        'Distributor': get_distributor_name(file_name),
                        'Sheet Name': sheet_name
                    }
                    
                    # Add city information if we have it for this row
                    if i in city_by_row:
                        row_data['City'] = city_by_row[i]
                    # Or try to find a city from a nearby row that has the same customer
                    else:
                        # Look in nearby rows with the same customer
                        for offset in range(1, 4):
                            if i-offset in city_by_row and i-offset in customer_by_row and customer_by_row[i-offset] == customer:
                                row_data['City'] = city_by_row[i-offset]
                                break
                            if i+offset in city_by_row and i+offset in customer_by_row and customer_by_row[i+offset] == customer:
                                row_data['City'] = city_by_row[i+offset]
                                break
                    
                    # Add state information if we have it for this row
                    if i in state_by_row:
                        row_data['State'] = state_by_row[i]
                    # Or try to find a state from a nearby row that has the same customer
                    else:
                        # Look in nearby rows with the same customer
                        for offset in range(1, 4):
                            if i-offset in state_by_row and i-offset in customer_by_row and customer_by_row[i-offset] == customer:
                                row_data['State'] = state_by_row[i-offset]
                                break
                            if i+offset in state_by_row and i+offset in customer_by_row and customer_by_row[i+offset] == customer:
                                row_data['State'] = state_by_row[i+offset]
                                break
                    
                    rows.append(row_data)
    
    if rows:
        print(f"Extracted {len(rows)} rows using asterisk product search")
        return pd.DataFrame(rows)
        
    return pd.DataFrame()

def extract_basic(df: pd.DataFrame, file_name: str, sheet_name: str) -> pd.DataFrame:
    """
    Fall back to basic extraction when other methods fail
    
    Args:
        df: Original dataframe
        file_name: Source file name
        sheet_name: Sheet name
        
    Returns:
        DataFrame with extracted data
    """
    # Look for customer/retailer column names and location info
    customer_col = None
    city_col = None
    state_col = None
    
    for col in df.columns:
        col_name = str(col).lower()
        if ('retailer' in col_name and 'name' in col_name) or ('customer' in col_name and 'name' in col_name):
            customer_col = col
            print(f"Found customer column: {col}")
        elif ('city' in col_name) or ('ship' in col_name and 'city' in col_name):
            city_col = col
            print(f"Found city column: {col}")
        elif ('state' in col_name) or ('ship' in col_name and 'state' in col_name):
            state_col = col
            print(f"Found state column: {col}")
    
    # Look for product columns with more specific patterns
    product_col = None
    
    # First, look for product columns containing real product names (having *)
    for col in df.columns:
        # Look at some sample values to see if they contain product patterns
        sample_values = df[col].dropna().astype(str).tolist()[:15]
        if any('*' in val for val in sample_values):
            product_col = col
            print(f"Found product column with * markers: {col}")
            break
    
    # If we didn't find a product column with * markers, look for traditional column names
    if not product_col:
        for col in df.columns:
            col_name = str(col).lower()
            if any(term in col_name for term in ['product', 'item', 'description', 'sku', 'mer/item']):
                # Verify this isn't just a numeric column
                sample_values = df[col].dropna().astype(str).tolist()[:15]
                # Skip columns that are mostly numbers
                if not all(val.replace('.', '').replace('-', '').isdigit() for val in sample_values if val):
                    product_col = col
                    print(f"Found product column by name: {col}")
                    break
    
    # If we still don't have a product column, we might be dealing with a Faire CSV or similar
    # where products aren't clearly labeled - use a fallback name
    if not product_col and customer_col and 'Retailer Name' in df.columns:
        # For Faire CSVs, use 'Order Number' as product identifier
        if 'Order Number' in df.columns:
            product_col = 'Order Number'
            print(f"Using Order Number as product identifier")
        else:
            # Look for a column containing product-like strings (not just numbers)
            for col in df.columns:
                if col != customer_col:
                    sample_values = df[col].dropna().astype(str).tolist()[:15]
                    if any(len(val) > 3 and not val.replace('.', '').replace('-', '').isdigit() 
                           for val in sample_values):
                        product_col = col
                        print(f"Using {col} as product identifier")
                        break
    
    if not customer_col:
        print("Could not identify customer column - cannot proceed with basic extraction")
        return pd.DataFrame()
    
    # Extract data
    rows = []
    
    # Set a default product name for files without product info
    default_product = "Hotpot Queen Product" if "hotpot" in sheet_name.lower() else "Distributor Product"
    
    for i, row in df.iterrows():
        # Get customer name
        customer = 'Unknown'
        if customer_col and pd.notna(row.get(customer_col)):
            customer = str(row[customer_col]).strip()
            # Skip headers, footers, and non-data rows
            if customer.lower() in ['retailer name', 'customer name', 'total', 'grand total', '']:
                continue
        
        # Get product name
        product = default_product
        if product_col and pd.notna(row.get(product_col)):
            product_val = str(row[product_col]).strip()
            # Skip headers, footers, and non-data rows
            if product_val.lower() in ['product', 'item', 'description', 'mer/item', 'total', '']:
                continue
                
            # Don't use pure numbers as product names
            if not product_val.replace('.', '').replace('-', '').isdigit():
                product = product_val
                
            # Check if this row has any * products in any column
            found_better_product = False
            for col in df.columns:
                if col != product_col and pd.notna(row.get(col)):
                    val = str(row[col]).strip()
                    if '*' in val and len(val) > 5:
                        # This looks like a proper product name with * marker
                        product = val
                        found_better_product = True
                        break
        
        # Look for quantity information
        quantity = 1  # Default
        
        # If the file is a faire.com CSV, use the Order Total for quantity
        if 'Order Total' in df.columns and pd.notna(row.get('Order Total')):
            try:
                order_total = str(row['Order Total']).replace('$', '').replace(',', '').strip()
                quantity = max(1, int(float(order_total)))
            except:
                pass
        else:
            # Try to find numeric columns that might contain quantities
            for col in df.columns:
                if col != product_col and col != customer_col and pd.notna(row.get(col)):
                    val = str(row[col]).strip()
                    # Check if this is a number that could be a quantity (not too big or too small)
                    try:
                        num_val = float(val.replace(',', ''))
                        if 0 < num_val < 1000:  # Reasonable quantity range
                            quantity = int(num_val)
                            break
                    except:
                        pass
        
        # Only add if we have a valid customer
        if customer != 'Unknown':
            # Create row data dictionary
            row_data = {
                'Customer Name': customer,
                'Product': product,
                'Quantity': quantity,
                'Source File': file_name,
                'Distributor': get_distributor_name(file_name),
                'Sheet Name': sheet_name
            }
            
            # Add city information if available
            if city_col and pd.notna(row.get(city_col)):
                city = str(row[city_col]).strip()
                if city and city.lower() not in ['city', 'ship city', 'n/a', '-']:
                    row_data['City'] = city
                    print(f"Found city for {customer}: {city}")
            
            # Add state information if available
            if state_col and pd.notna(row.get(state_col)):
                state = str(row[state_col]).strip()
                if state and state.lower() not in ['state', 'ship state', 'n/a', '-']:
                    row_data['State'] = state
                    print(f"Found state for {customer}: {state}")
            
            rows.append(row_data)
    
    # Filter out invalid rows and remove duplicates
    if rows:
        df_result = pd.DataFrame(rows)
        
        # Remove duplicates to avoid showing the same customer-product combination multiple times
        df_result = df_result.drop_duplicates(subset=['Customer Name', 'Product'])
        
        if not df_result.empty:
            print(f"Extracted {len(df_result)} rows using basic approach")
            return df_result
    
    return pd.DataFrame()
