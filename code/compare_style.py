import pandas as pd
import os

def analyze_style():
    sample_path = 'support_issues/sample_support_issues.csv'
    output_path = 'support_issues/output.csv'
    
    if not os.path.exists(sample_path) or not os.path.exists(output_path):
        print("Missing files.")
        return

    # Load data
    sample_df = pd.read_csv(sample_path)
    output_df = pd.read_csv(output_path)
    
    # Normalize column names for comparison
    sample_cols = [c.lower() for c in sample_df.columns]
    output_cols = [c.lower() for c in output_df.columns]
    
    print("--- Column Comparison ---")
    print(f"Sample Columns: {sample_cols}")
    print(f"Output Columns: {output_cols}")
    
    # Analyze Distributions
    def get_dist(df, col_name):
        # Find column regardless of casing
        actual_col = [c for c in df.columns if c.lower() == col_name.lower()]
        if not actual_col:
            return None
        return df[actual_col[0]].value_counts(normalize=True).to_dict()

    print("\n--- Status Distribution ---")
    print(f"Sample: {get_dist(sample_df, 'status')}")
    print(f"Output: {get_dist(output_df, 'status')}")
    
    print("\n--- Product Area Distribution ---")
    print(f"Sample: {get_dist(sample_df, 'Product Area')}")
    print(f"Output: {get_dist(output_df, 'product_area')}")

    print("\n--- Request Type Distribution ---")
    print(f"Sample: {get_dist(sample_df, 'Request Type')}")
    print(f"Output: {get_dist(output_df, 'request_type')}")

    # Response Style Analysis
    def analyze_response_style(df, col_name):
        actual_col = [c for c in df.columns if c.lower() == col_name.lower()]
        if not actual_col:
            return {}
        
        responses = df[actual_col[0]].dropna().astype(str)
        avg_len = responses.apply(len).mean()
        has_links = responses.apply(lambda x: 'http' in x).mean()
        has_markdown = responses.apply(lambda x: '#' in x or '**' in x).mean()
        
        return {
            "avg_length": avg_len,
            "pct_with_links": has_links,
            "pct_with_markdown": has_markdown
        }

    print("\n--- Response Style Analysis ---")
    print(f"Sample Style: {analyze_response_style(sample_df, 'Response')}")
    print(f"Output Style: {analyze_response_style(output_df, 'response')}")

if __name__ == "__main__":
    analyze_style()
