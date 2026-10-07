import os
import pandas as pd

def merge_csv_folder(folder_path: str, output_path: str = None) -> str:
    """Read all CSV files in folder_path, merge them vertically, and save to output_path.
    If output_path is None, saves to folder_path/merged.csv.
    Returns the path of the saved file."""
    csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.csv')]
    if not csv_files:
        raise FileNotFoundError("No CSV files found in the folder.")
    dfs = []
    for file in csv_files:
        df = pd.read_csv(os.path.join(folder_path, file))
        dfs.append(df)
    merged = pd.concat(dfs, ignore_index=True)
    out_path = output_path or os.path.join(folder_path, 'merged.csv')
    merged.to_csv(out_path, index=False)
    return out_path

# Test code
if __name__ == '__main__':
    import tempfile, json
    # Create temp folder with two csvs
    with tempfile.TemporaryDirectory() as tmp:
        df1 = pd.DataFrame({'a':[1,2], 'b':[3,4]})
        df2 = pd.DataFrame({'a':[5,6], 'b':[7,8]})
        df1.to_csv(os.path.join(tmp,'file1.csv'), index=False)
        df2.to_csv(os.path.join(tmp,'file2.csv'), index=False)
        out = merge_csv_folder(tmp)
        print('Merged file at:', out)
        merged_df = pd.read_csv(out)
        print(merged_df)
