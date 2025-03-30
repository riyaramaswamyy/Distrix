import streamlit as st
import pandas as pd
import os
import tempfile
from simple_data_processor import parse_distributor_files
from store_city_mapper import add_city_column

st.set_page_config(
    page_title="Distributor Report Analysis Dashboard",
    page_icon="📊",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'current_quarter' not in st.session_state:
    st.session_state.current_quarter = None
if 'quarters_available' not in st.session_state:
    st.session_state.quarters_available = []

def main():
    st.title("Distributor Report Analysis Dashboard")
    
    # Sidebar for file uploads and controls
    with st.sidebar:
        st.header("Upload Distributor Reports")
        st.write("Upload up to 5 Excel or CSV files from different distributors.")
        
        uploaded_files = st.file_uploader(
            "Choose files",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
            help="Upload distributor reports in Excel or CSV format",
        )
        
        process_button = st.button("Process Files", type="primary")
        
        if process_button and uploaded_files:
            if len(uploaded_files) > 5:
                st.error("Please upload no more than 5 files.")
            else:
                # Save files to temporary location
                temp_file_paths = []
                for file in uploaded_files:
                    # Determine file extension for the temporary file
                    file_extension = '.csv' if file.name.lower().endswith('.csv') else '.xlsx'
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
                        tmp.write(file.getvalue())
                        temp_file_paths.append(tmp.name)
                
                try:
                    # Process the Excel files with our simplified processor
                    processed_data = parse_distributor_files(temp_file_paths)
                    
                    if processed_data is None or processed_data.empty:
                        st.error("No valid data found in the uploaded files. Please check file formats.")
                    else:
                        # Store the processed data directly
                        st.session_state.processed_data = processed_data
                        
                        # Extract available quarters and ensure they're all strings
                        quarters = [str(q) for q in processed_data['Quarter'].unique()]
                        st.session_state.quarters_available = sorted(quarters)
                        
                        # Set default quarter to the most recent
                        if st.session_state.quarters_available:
                            st.session_state.current_quarter = st.session_state.quarters_available[-1]
                            
                        st.success(f"Successfully processed {len(uploaded_files)} files!")
                
                except Exception as e:
                    st.error(f"Error processing files: {str(e)}")
                
                # Clean up temporary files
                for path in temp_file_paths:
                    try:
                        os.unlink(path)
                    except:
                        pass
        
        # No quarter selector as requested
    
    # Main area
    if st.session_state.processed_data is None:
        st.info("👈 Upload Excel or CSV files from distributors to get started.")
        
        # Show sample instructions
        with st.expander("How to use this dashboard"):
            st.write("""
            ### Instructions:
            1. Upload up to 5 Excel or CSV files containing distributor reports using the sidebar.
            2. Click 'Process Files' to analyze the data.
            3. Use the dropdown menu to switch between different data views.
            
            ### Expected File Format:
            The system can handle different file formats (Excel and CSV), but they should generally contain:
            - Customer name
            - Product information
            - Quantity ordered
            """)
    else:
        # We have processed data, show the dashboard
        # Use all data instead of filtering by quarter
        all_data = st.session_state.processed_data.copy()
        
        # Display the basic dashboard
        st.header("Distributor Report Dashboard")
        
        # Basic metrics
        total_customers = all_data['Customer Name'].nunique()
        total_products = all_data['Product'].nunique()
        
        # Display metrics in columns
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Customers", f"{total_customers}")
        with col2:
            st.metric("Total Products", f"{total_products}")
            
        # Unified dashboard with dropdown selection
        st.subheader("Order Quantity Analytics")
        
        if not all_data.empty:
            # Create tabs for different views - Customer, City, and Distributor views
            view_options = ["By Customer", "By City", "By Distributor"]
            selected_view = st.selectbox("Select View", view_options)
            
            if selected_view == "By Customer":
                # Get customers with their total quantities
                chart_data = all_data.groupby('Customer Name')['Quantity'].sum().reset_index()
                chart_data = chart_data.sort_values('Quantity', ascending=False)
                
                # Show the chart (static, not moveable)
                st.bar_chart(
                    data=chart_data.set_index('Customer Name'),
                    use_container_width=True,
                    height=400
                )
                
                # Also show the detailed data in a table
                st.subheader("Customer Details")
                st.dataframe(
                    chart_data,
                    column_config={
                        "Customer Name": st.column_config.TextColumn("Customer Name"),
                        "Quantity": st.column_config.NumberColumn("Total Ordered", format="%d")
                    },
                    use_container_width=True
                )
                
            elif selected_view == "By City":
                # Add city mapping to the data
                mapped_data = add_city_column(all_data)
                
                # Get quantities by city
                city_data = mapped_data.groupby('City')['Quantity'].sum().reset_index()
                city_data = city_data.sort_values('Quantity', ascending=False)
                
                # Count stores per city
                stores_count = mapped_data.groupby('City')['Customer Name'].nunique().reset_index()
                stores_count.columns = ['City', 'Store Count']
                
                # Combine the data
                chart_data = pd.merge(city_data, stores_count, on='City', how='left')
                
                # Display the bar chart
                st.subheader("Orders by City")
                st.bar_chart(
                    data=city_data.set_index('City'), 
                    use_container_width=True,
                    height=400
                )
                
                # Show the data table
                st.subheader("City Details")
                st.write("Cities with order quantities and store counts:")
                st.dataframe(chart_data, use_container_width=True)
                
            elif selected_view == "By Distributor":
                # Get order quantity by distributor
                dist_quantity = all_data.groupby('Distributor')['Quantity'].sum().reset_index()
                dist_quantity = dist_quantity.sort_values('Quantity', ascending=False)
                
                # Display the bar chart
                st.subheader("Orders by Distributor")
                st.bar_chart(
                    data=dist_quantity.set_index('Distributor'),
                    use_container_width=True,
                    height=400
                )
                
                # Show the data table
                st.subheader("Distributor Details")
                st.write("Distributors with total order quantities:")
                # Use simple dataframe display without column_config to avoid errors
                st.dataframe(
                    dist_quantity.rename(columns={"Quantity": "Total Ordered"}),
                    use_container_width=True
                )
        else:
            st.info("No data found. Please upload some files.")
            
        # Raw Data View
        with st.expander("View Raw Data"):
            # Ensure we display the Distributor column first
            columns_to_display = ['Distributor', 'Customer Name', 'Product', 'Quantity'] + [
                col for col in all_data.columns 
                if col not in ['Distributor', 'Customer Name', 'Product', 'Quantity']
            ]
            st.dataframe(all_data[columns_to_display], use_container_width=True)

if __name__ == "__main__":
    main()
