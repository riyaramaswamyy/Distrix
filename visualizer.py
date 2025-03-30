import streamlit as st
import pandas as pd
import re
from typing import List, Dict, Tuple

def create_quarterly_dashboard(quarter_data: pd.DataFrame, quarter: str) -> None:
    """
    Create the main quarterly dashboard with key metrics using simple Streamlit elements.
    
    Args:
        quarter_data: Dataframe with data for the selected quarter
        quarter: Selected quarter (e.g., "Q1 2023")
    """
    # Ensure we have a valid quarter string
    if pd.isna(quarter) or 'nan' in str(quarter).lower():
        quarter = "Current Quarter"
    
    st.header(f"Quarterly Overview: {quarter}")
    
    try:
        # Calculate key metrics safely
        quarter_data_safe = quarter_data.copy()
        # Ensure Quantity is numeric
        quarter_data_safe['Quantity'] = pd.to_numeric(quarter_data_safe['Quantity'], errors='coerce').fillna(0)
        
        # Calculate metrics
        total_stores = quarter_data_safe['Customer Name'].nunique()
        total_products = quarter_data_safe['Product'].nunique()
        total_orders = quarter_data_safe.shape[0]
        total_quantity = quarter_data_safe['Quantity'].sum()
        
        # Create a clean layout for metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Stores", f"{total_stores:,}")
        
        with col2:
            st.metric("Products Distributed", f"{total_products:,}")
        
        with col3:
            st.metric("Total Orders", f"{total_orders:,}")
        
        with col4:
            st.metric("Total Quantity", f"{total_quantity:,.0f}")
        
        # Show monthly distribution if available
        display_monthly_order_summary(quarter_data_safe)
        
    except Exception as e:
        st.error(f"Error in dashboard metrics: {str(e)}")

def display_monthly_order_summary(data: pd.DataFrame) -> None:
    """
    Display a simple month-by-month order summary using Streamlit native elements.
    
    Args:
        data: Processed dataframe
    """
    if 'Month' not in data.columns or data.empty:
        return
    
    st.subheader("Monthly Order Summary")
    
    try:
        # Clean month data and convert to numeric safely
        data['Month'] = pd.to_numeric(data['Month'], errors='coerce')
        valid_months = data[data['Month'].between(1, 12)]
        
        if valid_months.empty:
            st.info("No valid month data available.")
            return
        
        # Convert months to integer
        valid_months['Month'] = valid_months['Month'].astype(int)
        
        # Group by month and sum quantities
        monthly_summary = valid_months.groupby('Month').agg({
            'Quantity': 'sum',
            'Customer Name': 'nunique',
            'Product': 'nunique'
        }).reset_index()
        
        # Add month names
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April', 
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        monthly_summary['Month Name'] = monthly_summary['Month'].map(month_names)
        
        # Sort by month number
        monthly_summary = monthly_summary.sort_values('Month')
        
        # Display as a formatted table
        table_data = monthly_summary[['Month Name', 'Quantity', 'Customer Name', 'Product']]
        table_data = table_data.rename(columns={
            'Month Name': 'Month',
            'Customer Name': 'Unique Customers',
            'Product': 'Unique Products'
        })
        
        # Use Streamlit's native dataframe display with formatting
        st.dataframe(
            table_data,
            column_config={
                "Month": st.column_config.TextColumn("Month"),
                "Quantity": st.column_config.NumberColumn("Total Quantity", format="%d"),
                "Unique Customers": st.column_config.NumberColumn("Unique Customers", format="%d"),
                "Unique Products": st.column_config.NumberColumn("Unique Products", format="%d")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Create a simple text-based bar chart as a backup visual
        st.subheader("Monthly Order Distribution")
        
        # Calculate max for scaling
        max_qty = monthly_summary['Quantity'].max()
        if max_qty > 0:
            scale_factor = 100 / max_qty
            
            for _, row in monthly_summary.iterrows():
                month_name = row['Month Name']
                qty = row['Quantity']
                bar_length = int(qty * scale_factor)
                
                # Create a formatted bar
                st.write(f"{month_name}: {qty:,}")
                st.progress(min(bar_length/100, 1.0))
                
    except Exception as e:
        st.error(f"Error processing monthly data: {str(e)}")

def display_product_distribution(quarter_data: pd.DataFrame) -> None:
    """
    Show product distribution details using simple Streamlit elements.
    
    Args:
        quarter_data: DataFrame with quarterly data
    """
    st.subheader("Product Distribution")
    
    try:
        # Clean data
        df = quarter_data.copy()
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        
        # Get product distribution stats
        product_stats = df.groupby('Product').agg({
            'Customer Name': lambda x: x.nunique(),
            'Quantity': 'sum'
        }).reset_index()
        
        # Rename columns
        product_stats.columns = ['Product', 'Store Count', 'Total Quantity']
        
        # Sort by store count
        product_stats = product_stats.sort_values('Store Count', ascending=False)
        
        # Display as a table
        st.dataframe(
            product_stats,
            column_config={
                "Product": st.column_config.TextColumn("Product"),
                "Store Count": st.column_config.NumberColumn("Number of Stores", format="%d"),
                "Total Quantity": st.column_config.NumberColumn("Total Quantity", format="%d")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Show visual representation of top products
        st.subheader("Top Products by Store Coverage")
        
        # Get top 5 products by store count
        top_products = product_stats.head(5)
        
        for _, row in top_products.iterrows():
            product = row['Product']
            store_count = row['Store Count']
            total_qty = row['Total Quantity']
            
            # Calculate percentage of stores carrying this product
            store_percentage = (store_count / quarter_data['Customer Name'].nunique()) * 100
            
            # Create a formatted display with progress bar
            st.write(f"**{product}**: In {store_count} stores ({store_percentage:.1f}%), Total Qty: {total_qty:,}")
            st.progress(min(store_percentage/100, 1.0))
        
    except Exception as e:
        st.error(f"Error creating product distribution display: {str(e)}")

def display_quarterly_comparison(all_data: pd.DataFrame, current_quarter: str) -> None:
    """
    Show a quarter-by-quarter comparison using simple tabular format.
    
    Args:
        all_data: Complete dataset
        current_quarter: Currently selected quarter
    """
    st.subheader("Quarterly Comparison")
    
    try:
        # Clean data
        df = all_data.copy()
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        
        # Filter valid quarters
        df = df[df['Quarter'].notna()]
        df = df[~df['Quarter'].astype(str).str.contains('nan', case=False)]
        
        if df.empty:
            st.info("No valid quarter data available.")
            return
        
        # Group by quarter
        quarterly_summary = df.groupby('Quarter').agg({
            'Customer Name': 'nunique',
            'Product': 'nunique',
            'Quantity': 'sum'
        }).reset_index()
        
        # Rename columns for clarity
        quarterly_summary.columns = ['Quarter', 'Unique Customers', 'Unique Products', 'Total Quantity']
        
        # Try to sort quarters chronologically if possible
        try:
            # Extract year and quarter number using regex
            pattern = r'Q(\d+)\s+(\d{4})'
            
            def extract_year_quarter(quarter_str):
                match = re.search(pattern, str(quarter_str))
                if match:
                    q_num = int(match.group(1))
                    year = int(match.group(2))
                    return year * 10 + q_num
                return 99999  # Default sorting value
            
            # Add sort key
            quarterly_summary['sort_key'] = quarterly_summary['Quarter'].apply(extract_year_quarter)
            
            # Sort and remove the key
            quarterly_summary = quarterly_summary.sort_values('sort_key')
            quarterly_summary = quarterly_summary.drop('sort_key', axis=1)
        except:
            # If sorting fails, leave as is
            pass
        
        # Highlight current quarter in the display
        def highlight_current(row):
            if row['Quarter'] == current_quarter:
                return ['background-color: rgba(0, 97, 255, 0.1)'] * len(row)
            return [''] * len(row)
        
        # Display as a styled dataframe
        st.dataframe(
            quarterly_summary,
            column_config={
                "Quarter": st.column_config.TextColumn("Quarter"),
                "Unique Customers": st.column_config.NumberColumn("Customers", format="%d"),
                "Unique Products": st.column_config.NumberColumn("Products", format="%d"),
                "Total Quantity": st.column_config.NumberColumn("Quantity", format="%d")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Calculate quarter-over-quarter changes if more than one quarter
        if len(quarterly_summary) > 1:
            st.subheader("Quarter-over-Quarter Changes")
            
            try:
                # Get the current quarter's stats
                current_stats = quarterly_summary[quarterly_summary['Quarter'] == current_quarter]
                
                if not current_stats.empty:
                    # Find the previous quarter
                    current_idx = quarterly_summary[quarterly_summary['Quarter'] == current_quarter].index[0]
                    
                    if current_idx > 0:
                        prev_idx = current_idx - 1
                        prev_quarter = quarterly_summary.iloc[prev_idx]
                        curr_quarter = quarterly_summary.iloc[current_idx]
                        
                        # Calculate changes
                        customer_change = curr_quarter['Unique Customers'] - prev_quarter['Unique Customers']
                        product_change = curr_quarter['Unique Products'] - prev_quarter['Unique Products']
                        quantity_change = curr_quarter['Total Quantity'] - prev_quarter['Total Quantity']
                        
                        # Calculate percentage changes
                        customer_pct = (customer_change / prev_quarter['Unique Customers'] * 100) if prev_quarter['Unique Customers'] > 0 else 0
                        product_pct = (product_change / prev_quarter['Unique Products'] * 100) if prev_quarter['Unique Products'] > 0 else 0
                        quantity_pct = (quantity_change / prev_quarter['Total Quantity'] * 100) if prev_quarter['Total Quantity'] > 0 else 0
                        
                        # Display metrics with delta values
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric(
                                "Customer Change", 
                                f"{curr_quarter['Unique Customers']}", 
                                f"{customer_change:+g} ({customer_pct:+.1f}%)"
                            )
                        
                        with col2:
                            st.metric(
                                "Product Change", 
                                f"{curr_quarter['Unique Products']}", 
                                f"{product_change:+g} ({product_pct:+.1f}%)"
                            )
                        
                        with col3:
                            st.metric(
                                "Quantity Change", 
                                f"{curr_quarter['Total Quantity']:,}", 
                                f"{quantity_change:+,g} ({quantity_pct:+.1f}%)"
                            )
            except Exception as e:
                st.error(f"Error calculating quarter changes: {str(e)}")
        
    except Exception as e:
        st.error(f"Error creating quarterly comparison: {str(e)}")

def display_customer_locations(quarter_data: pd.DataFrame) -> None:
    """
    Display customer location information with simple visuals.
    
    Args:
        quarter_data: DataFrame with quarterly data
    """
    st.subheader("Customer Locations")
    
    try:
        # Check if state data is available
        if 'State' not in quarter_data.columns or quarter_data.empty:
            st.info("No location data available.")
            return
        
        # Count customers by state
        state_counts = quarter_data.groupby('State')['Customer Name'].nunique().reset_index()
        state_counts.columns = ['State', 'Customer Count']
        
        # Sort by customer count
        state_counts = state_counts.sort_values('Customer Count', ascending=False)
        
        # Calculate percentages
        total_customers = state_counts['Customer Count'].sum()
        state_counts['Percentage'] = (state_counts['Customer Count'] / total_customers * 100).round(1)
        
        # Display as table
        st.dataframe(
            state_counts,
            column_config={
                "State": st.column_config.TextColumn("State"),
                "Customer Count": st.column_config.NumberColumn("Customers", format="%d"),
                "Percentage": st.column_config.NumberColumn("% of Total", format="%.1f%%")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Show top states with progress bars
        st.subheader("Top States by Customer Count")
        top_states = state_counts.head(5)
        
        for _, row in top_states.iterrows():
            state = row['State']
            count = row['Customer Count']
            percentage = row['Percentage']
            
            st.write(f"**{state}**: {count} customers ({percentage}%)")
            st.progress(min(percentage/100, 1.0))
        
    except Exception as e:
        st.error(f"Error creating location display: {str(e)}")

def display_top_customers(quarter_data: pd.DataFrame) -> None:
    """
    Display top customers by order quantity.
    
    Args:
        quarter_data: DataFrame with quarterly data
    """
    st.subheader("Top Customers by Order Volume")
    
    try:
        # Clean data
        df = quarter_data.copy()
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        
        # Group by customer
        customer_stats = df.groupby('Customer Name').agg({
            'Product': 'nunique',
            'Quantity': 'sum'
        }).reset_index()
        
        # Rename columns
        customer_stats.columns = ['Customer Name', 'Unique Products', 'Total Quantity']
        
        # Sort by total quantity
        customer_stats = customer_stats.sort_values('Total Quantity', ascending=False)
        
        # Display top 10 customers
        st.dataframe(
            customer_stats.head(10),
            column_config={
                "Customer Name": st.column_config.TextColumn("Customer"),
                "Unique Products": st.column_config.NumberColumn("Products", format="%d"),
                "Total Quantity": st.column_config.NumberColumn("Order Quantity", format="%d")
            },
            use_container_width=True,
            hide_index=True
        )
        
    except Exception as e:
        st.error(f"Error creating top customers display: {str(e)}")
