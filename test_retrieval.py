import sys
import retriever
import re

def main():
    query = 'check if a website is up'
    print(f"Executing search_skills('{query}')")
    
    # Run the retriever search
    top_results = retriever.search_skills(query)
    
    print("\n--- RAW OUTPUT FROM RETRIEVER ---")
    for r in top_results:
        print(f"Title: {r.get('title')}")
        print(f"Score: {r.get('score')}")
        print(f"Tags: {r.get('tags')}")
        print("---")
        
    print("\n--- RELEVANCE GATE CHECK ---")
    user_words = set(re.findall(r'\w+', query.lower()))
    for candidate in top_results[:3]:
        tags = candidate.get('tags', '') or ''
        cand_words = set(re.findall(r'\w+', tags.lower()))
        
        overlap = len(user_words.intersection(cand_words))
        score = candidate.get('score', 0)
        
        if overlap == 0 and score < 0.85:
            print(f"Candidate: '{candidate.get('title')}' -> Score: {score} (Discarded: No keyword overlap).")
        else:
            print(f"Candidate: '{candidate.get('title')}' -> Score: {score} (Kept: Keyword overlap {overlap} or High Score).")

if __name__ == "__main__":
    main()
