import pandas as pd
import mysql.connector
from mysql.connector import Error
import numpy as np

DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_db',
    'user': 'root',
    'password': 'YOUR_MYSQL_ROOT_PASSWORD',
    'ssl_disabled': True,
    'auth_plugin': 'mysql_native_password'
}

BATCH_SIZE = 5000

def create_db_connection():
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print("Successfully connected to MySQL database.")
            return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
    return connection

def load_csv_to_mysql(file_path, table_name, connection, columns_map=None, date_cols=None, dataframe=None):
    print(f"Loading {file_path if file_path else 'DataFrame'} into table: {table_name}")

    if dataframe is not None:
        df = dataframe.copy()
    else:
        df = pd.read_csv(file_path)

    if table_name == 'users':
        initial_rows = len(df)
        df.drop_duplicates(subset=['email'], inplace=True, keep='first')
        if len(df) < initial_rows:
            print(f"Removed {initial_rows - len(df)} duplicate email entries from {file_path}.")

    if date_cols:
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

    df = df.replace({np.nan: None})

    cursor = connection.cursor()

    if columns_map:
        df_for_insert = df[list(columns_map.keys())].rename(columns=columns_map)
        cols_to_insert = list(columns_map.values())
    else:
        df_for_insert = df.copy()
        cols_to_insert = df_for_insert.columns.tolist()

    placeholders = ', '.join(['%s'] * len(cols_to_insert))
    columns_str = ', '.join(cols_to_insert)
    insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

    total_inserted = 0
    for i in range(0, len(df_for_insert), BATCH_SIZE):
        batch = df_for_insert[i:i + BATCH_SIZE]
        data_to_insert = batch[cols_to_insert].values.tolist()

        if data_to_insert:
            try:
                cursor.executemany(insert_query, data_to_insert)
                connection.commit()
                total_inserted += cursor.rowcount
                print(f"  Inserted batch {i // BATCH_SIZE + 1} ({cursor.rowcount} records) into {table_name}.")
            except Error as e:
                print(f"Error inserting batch into {table_name} (starting at row {i}): {e}")
                connection.rollback()
                print("Stopping further insertions for this table due to error in batch.")
                break

    print(f"Successfully inserted {total_inserted} total records into {table_name}.")
    cursor.close()
    return df


def get_existing_ids(connection, table_name, id_column):
    cursor = connection.cursor()
    query = f"SELECT {id_column} FROM {table_name}"
    try:
        cursor.execute(query)
        ids = {row[0] for row in cursor.fetchall()}
        return ids
    except Error as e:
        print(f"Error fetching IDs from {table_name}: {e}")
        return set()
    finally:
        cursor.close()

if __name__ == "__main__":
    conn = create_db_connection()

    if conn:
        print("\n--- Starting Data Load ---")

        load_csv_to_mysql(
            'distribution_centers.csv',
            'distribution_centers',
            conn
        )

        load_csv_to_mysql(
            'products.csv',
            'products',
            conn,
            date_cols=[]
        )

        users_df_raw = pd.read_csv('users.csv')
        load_csv_to_mysql(
            'users.csv',
            'users',
            conn,
            date_cols=['created_at'],
            dataframe=users_df_raw
        )

        existing_user_ids = get_existing_ids(conn, 'users', 'id')
        print(f"Found {len(existing_user_ids)} unique user IDs in the database for orders filtering.")

        orders_df_raw = pd.read_csv('orders.csv')
        initial_orders_rows = len(orders_df_raw)
        orders_df_filtered = orders_df_raw[orders_df_raw['user_id'].isin(existing_user_ids)].copy()
        if len(orders_df_filtered) < initial_orders_rows:
            print(f"Removed {initial_orders_rows - len(orders_df_filtered)} orders due to non-existent user_id.")

        load_csv_to_mysql(
            None,
            'orders',
            conn,
            columns_map={'order_id': 'order_id', 'user_id': 'user_id', 'status': 'status',
                         'gender': 'gender', 'created_at': 'created_at', 'returned_at': 'returned_at',
                         'shipped_at': 'shipped_at', 'delivered_at': 'delivered_at',
                         'num_of_item': 'num_of_item'},
            date_cols=['created_at', 'returned_at', 'shipped_at', 'delivered_at'],
            dataframe=orders_df_filtered
        )

        load_csv_to_mysql(
            'inventory_items.csv',
            'inventory_items',
            conn,
            columns_map={'id': 'id', 'product_id': 'product_id', 'created_at': 'created_at',
                         'sold_at': 'sold_at', 'cost': 'cost', 'product_category': 'product_category',
                         'product_name': 'product_name', 'product_brand': 'product_brand',
                         'product_retail_price': 'product_retail_price', 'product_department': 'product_department',
                         'product_sku': 'product_sku', 'product_distribution_center_id': 'product_distribution_center_id'},
            date_cols=['created_at', 'sold_at']
        )

        existing_product_ids = get_existing_ids(conn, 'products', 'id')
        existing_inventory_item_ids = get_existing_ids(conn, 'inventory_items', 'id')
        existing_order_ids = get_existing_ids(conn, 'orders', 'order_id')
        print(f"Found {len(existing_product_ids)} product IDs, {len(existing_inventory_item_ids)} inventory item IDs, and {len(existing_order_ids)} order IDs for order_items filtering.")

        order_items_df_raw = pd.read_csv('order_items.csv')
        initial_order_items_rows = len(order_items_df_raw)

        order_items_df_filtered = order_items_df_raw[
            order_items_df_raw['order_id'].isin(existing_order_ids) &
            order_items_df_raw['user_id'].isin(existing_user_ids) &
            order_items_df_raw['product_id'].isin(existing_product_ids) &
            order_items_df_raw['inventory_item_id'].isin(existing_inventory_item_ids)
        ].copy()

        if len(order_items_df_filtered) < initial_order_items_rows:
            print(f"Removed {initial_order_items_rows - len(order_items_df_filtered)} order_items due to non-existent foreign keys.")

        load_csv_to_mysql(
            None,
            'order_items',
            conn,
            columns_map={'id': 'id', 'order_id': 'order_id', 'user_id': 'user_id',
                         'product_id': 'product_id', 'inventory_item_id': 'inventory_item_id',
                         'status': 'status', 'created_at': 'created_at', 'shipped_at': 'shipped_at',
                         'delivered_at': 'delivered_at', 'returned_at': 'returned_at',
                         'sale_price': 'sale_price'},
            date_cols=['created_at', 'shipped_at', 'delivered_at', 'returned_at'],
            dataframe=order_items_df_filtered
        )

        conn.close()
        print("--- Data loading complete and MySQL connection closed. ---")
    else:
        print("Failed to establish database connection. Data loading aborted.")