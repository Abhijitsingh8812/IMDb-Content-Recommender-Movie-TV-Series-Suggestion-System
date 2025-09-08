import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
import time
from PIL import Image
import io
import base64
from urllib.parse import urljoin

class ContentRecommender:
    def __init__(self):
        self.valid_genres = [
            'biography', 'drama', 'gangster', 'musical', 'romance',
            'sci-fi', 'epic', 'mystery', 'history', 'documentary',
            'action', 'animation', 'comedy', 'family', 'adventure',
            'film noir', 'fantasy', 'music', 'western', 'horror',
            'thriller', 'crime', 'sport'
        ]
        self.base_url = "https://www.imdb.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.emoji_map = {
            'movie': '🎬',
            'tv': '📺',
            'both': '🎥',
            'star': '⭐',
            'clapper': '🎬',
            'popcorn': '🍿',
            'tv_show': '📺',
            'camera': '📷'
        }

    def get_user_preferences(self):
        """Prompt user for genre preferences and validate input"""
        print("\n🎬 Welcome to your personalized content recommender! 🎬")
        print("I'll help you discover movies and series based on your taste.\n")

        while True:
            # Display genres horizontally
            genre_display = ", ".join([f"{i+1}. {genre.capitalize()}" for i, genre in enumerate(self.valid_genres)])
            print(f"\nAvailable genres: {genre_display}")

            user_input = input("\nEnter 1-3 genres (comma separated): ").lower().strip()
            genres = re.split(r',|\s+and\s+', user_input)
            genres = [g.strip() for g in genres if g.strip()]

            if not 1 <= len(genres) <= 3:
                print("⚠️ Please select 1-3 genres only.")
                continue

            invalid = [g for g in genres if g not in self.valid_genres]
            if invalid:
                print(f"⚠️ Invalid genres: {', '.join(invalid)}. Please choose from the list.")
                continue

            # Ask for content type
            print("\nWhat type of content are you interested in?")
            print(f"🎬 M - Movies only")
            print(f"📺 S - TV Series and Web Series")
            print(f"🎥 B - Both Movies and TV Series")

            content_type = input("\nEnter your choice (M/S/B): ").upper().strip()
            while content_type not in ['M', 'S', 'B']:
                print("⚠️ Please enter M, S, or B")
                content_type = input("Enter your choice (M/S/B): ").upper().strip()

            return genres, content_type

    def search_imdb(self, genres, content_type):
        """Search IMDb for content matching user preferences"""
        results = []
        search_urls = self._create_search_urls(genres, content_type)

        print(f"\n🔍 Searching IMDb for {', '.join(genres)} content... This may take a moment.")

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._scrape_search_page, url) for url in search_urls]

            for future in futures:
                try:
                    page_results = future.result()
                    results.extend(page_results)
                except Exception as e:
                    print(f"⚠️ Search error: {str(e)}")

        # Remove duplicates and sort by rating
        unique_results = {item['title']: item for item in results}.values()
        sorted_results = sorted(unique_results, key=lambda x: x['rating'], reverse=True)

        return sorted_results[:10]

    def _create_search_urls(self, genres, content_type):
        """Create IMDb search URLs based on genres and content type"""
        urls = []
        genre_params = {
            'biography': 'genres=biography',
            'drama': 'genres=drama',
            'gangster': 'genres=crime',
            'musical': 'genres=musical',
            'romance': 'genres=romance',
            'sci-fi': 'genres=sci-fi',
            'epic': 'genres=adventure',
            'mystery': 'genres=mystery',
            'history': 'genres=history',
            'documentary': 'genres=documentary',
            'action': 'genres=action',
            'animation': 'genres=animation',
            'comedy': 'genres=comedy',
            'family': 'genres=family',
            'adventure': 'genres=adventure',
            'film-noir': 'genres=film-noir',
            'fantasy': 'genres=fantasy',
            'music': 'genres=music',
            'western': 'genres=western',
            'horror': 'genres=horror',
            'thriller': 'genres=thriller',
            'crime': 'genres=crime',
            'sport': 'genres=sport'
        }

        # Determine title type based on content type
        title_type = ""
        if content_type == 'M':
            title_type = "&title_type=feature"
        elif content_type == 'S':
            title_type = "&title_type=tv_series"

        # Create individual genre searches
        for genre in genres:
            param = genre_params.get(genre, f'genres={genre}')
            urls.append(f"{self.base_url}/search/title/?{param}{title_type}&sort=user_rating,desc")

        # Create combined genre search
        combined_params = '&'.join([genre_params[g] for g in genres if g in genre_params])
        if combined_params:
            urls.append(f"{self.base_url}/search/title/?{combined_params}{title_type}&sort=user_rating,desc")

        return urls

    def _scrape_search_page(self, url):
        """Scrape a single IMDb search results page"""
        results = []
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all movie items
            items = soup.select('.ipc-metadata-list-summary-item')

            for item in items[:10]:  # Limit to first 10 results per page
                try:
                    title_elem = item.select_one('.ipc-title__text')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = item.select_one('a.ipc-title-link-wrapper')['href']
                    full_link = f"{self.base_url}{link.split('?')[0]}"

                    # Extract year
                    year_elem = item.select_one('.dli-title-metadata-item')
                    year = year_elem.get_text(strip=True) if year_elem else "N/A"

                    # Extract rating
                    rating_elem = item.select_one('.ipc-rating-star')
                    rating = rating_elem.get_text(strip=True).split()[0] if rating_elem else "N/A"

                    # Extract image
                    image_elem = item.select_one('img.ipc-image')
                    image_url = image_elem.get('src') if image_elem else None

                    # Get synopsis
                    synopsis = self._get_synopsis(full_link)

                    results.append({
                        'title': title,
                        'year': year,
                        'rating': rating,
                        'synopsis': synopsis,
                        'link': full_link,
                        'image_url': image_url
                    })

                except Exception as e:
                    print(f"⚠️ Error processing item: {str(e)}")
                    continue

        except Exception as e:
            print(f"⚠️ Error scraping {url}: {str(e)}")

        return results

    def _get_synopsis(self, url):
        """Get movie synopsis from its detail page"""
        try:
            response = self.session.get(url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Try multiple selectors for synopsis
            synopsis_selectors = [
                '.ipc-html-content-inner-div',
                '.plot_summary .summary_text',
                '.canwrap .plotxl'
            ]

            for selector in synopsis_selectors:
                synopsis_elem = soup.select_one(selector)
                if synopsis_elem:
                    synopsis = synopsis_elem.get_text(strip=True)
                    # Clean up common synopsis text
                    synopsis = re.sub(r'Written by.*$', '', synopsis)
                    synopsis = re.sub(r'—.*$', '', synopsis)
                    return synopsis[:200] + "..." if len(synopsis) > 200 else synopsis

            return "Synopsis not available"
        except:
            return "Synopsis not available"

    def _resize_image(self, image_url, size=(100, 150)):
        """Resize image to small thumbnail"""
        try:
            response = self.session.get(image_url, timeout=5)
            img = Image.open(io.BytesIO(response.content))
            img.thumbnail(size)

            # Convert to base64 for terminal display
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return img_str
        except:
            return None

    def display_recommendations(self, recommendations):
        """Display formatted recommendations with images"""
        if not recommendations:
            print("⚠️ No matches found. Try different genres.")
            return

        print(f"\n🎉 Here are your personalized recommendations: 🎉")

        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec['title']} ({rec['year']})")
            print(f"   {self.emoji_map['star']} IMDb Rating: {rec['rating']}/10")
            print(f"   {self.emoji_map['star']} Synopsis: {rec['synopsis']}")
            print(f"   {self.emoji_map['star']} Link: {rec['link']}")

            # Display image if available
            if rec['image_url']:
                print(f"   {self.emoji_map['camera']} Image: {rec['image_url']}")

                # Try to display a small thumbnail in terminal
                img_data = self._resize_image(rec['image_url'])
                if img_data:
                    print("\n   [Small thumbnail preview]")
                    # This will display the image in terminals that support base64 images
                    print(f"\033]1337;File=inline=1;width=30;height=40;:{img_data}\a")

    def run(self):
        """Main recommendation workflow"""
        while True:
            # Get user preferences
            genres, content_type = self.get_user_preferences()

            # Search and display recommendations
            recommendations = self.search_imdb(genres, content_type)
            self.display_recommendations(recommendations)

            # Ask if user wants to search again
            choice = input(f"\n{self.emoji_map['popcorn']} Would you like to search again? (yes/no): ").lower()
            if choice not in ['yes', 'y']:
                print(f"\n{self.emoji_map['clapper']} Enjoy your viewing! {self.emoji_map['popcorn']}")
                break

if __name__ == "__main__":
    recommender = ContentRecommender()
    recommender.run()

import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
import time

class ContentRecommender:
    def __init__(self):
        self.valid_genres = [
            'biography', 'drama', 'gangster', 'musical', 'romance',
            'sci-fi', 'epic', 'mystery', 'history', 'documentary',
            'action', 'animation', 'comedy', 'family', 'adventure',
            'film noir', 'fantasy', 'music', 'western', 'horror',
            'thriller', 'crime', 'sport', 'anime'  # Added anime genre
        ]
        self.base_url = "https://www.imdb.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.emoji_map = {
            'movie': '🎬',
            'tv': '📺',
            'both': '🎥',
            'star': '⭐',
            'clapper': '🎬',
            'popcorn': '🍿',
            'tv_show': '📺',
            'anime': '🎌'  # Added emoji for anime
        }

    def get_user_preferences(self):
        """Prompt user for genre preferences and validate input"""
        print("\n🎬 Welcome to your personalized content recommender! 🎬")
        print("I'll help you discover movies and series based on your taste.\n")

        while True:
            # Display genres horizontally
            genre_display = ", ".join([f"{i+1}. {genre.capitalize()}" for i, genre in enumerate(self.valid_genres)])
            print(f"\nAvailable genres: {genre_display}")

            user_input = input("\nEnter 1-3 genres (comma separated): ").lower().strip()
            genres = re.split(r',|\s+and\s+', user_input)
            genres = [g.strip() for g in genres if g.strip()]

            if not 1 <= len(genres) <= 3:
                print("⚠️ Please select 1-3 genres only.")
                continue

            invalid = [g for g in genres if g not in self.valid_genres]
            if invalid:
                print(f"⚠️ Invalid genres: {', '.join(invalid)}. Please choose from the list.")
                continue

            # Ask for content type
            print("\nWhat type of content are you interested in?")
            print(f"🎬 M - Movies only")
            print(f"📺 S - TV Series and Web Series")
            print(f"🎥 B - Both Movies and TV Series")

            content_type = input("\nEnter your choice (M/S/B): ").upper().strip()
            while content_type not in ['M', 'S', 'B']:
                print("⚠️ Please enter M, S, or B")
                content_type = input("Enter your choice (M/S/B): ").upper().strip()

            return genres, content_type

    def search_imdb(self, genres, content_type):
        """Search IMDb for content matching user preferences"""
        results = []
        search_urls = self._create_search_urls(genres, content_type)

        print(f"\n🔍 Searching IMDb for {', '.join(genres)} content... This may take a moment.")

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._scrape_search_page, url) for url in search_urls]

            for future in futures:
                try:
                    page_results = future.result()
                    results.extend(page_results)
                except Exception as e:
                    print(f"⚠️ Search error: {str(e)}")

        # Remove duplicates and sort by rating
        unique_results = {item['title']: item for item in results}.values()
        sorted_results = sorted(unique_results, key=lambda x: x['rating'], reverse=True)

        return sorted_results[:10]

    def _create_search_urls(self, genres, content_type):
        """Create IMDb search URLs based on genres and content type"""
        urls = []
        genre_params = {
            'biography': 'genres=biography',
            'drama': 'genres=drama',
            'gangster': 'genres=crime',
            'musical': 'genres=musical',
            'romance': 'genres=romance',
            'sci-fi': 'genres=sci-fi',
            'epic': 'genres=adventure',
            'mystery': 'genres=mystery',
            'history': 'genres=history',
            'documentary': 'genres=documentary',
            'action': 'genres=action',
            'animation': 'genres=animation',
            'comedy': 'genres=comedy',
            'family': 'genres=family',
            'adventure': 'genres=adventure',
            'film-noir': 'genres=film-noir',
            'fantasy': 'genres=fantasy',
            'music': 'genres=music',
            'western': 'genres=western',
            'horror': 'genres=horror',
            'thriller': 'genres=thriller',
            'crime': 'genres=crime',
            'sport': 'genres=sport',
            'anime': 'genres=animation'  # Map anime to animation for IMDb search
        }

        # Determine title type based on content type
        title_type = ""
        if content_type == 'M':
            title_type = "&title_type=feature"
        elif content_type == 'S':
            title_type = "&title_type=tv_series"

        # Create individual genre searches
        for genre in genres:
            param = genre_params.get(genre, f'genres={genre}')
            urls.append(f"{self.base_url}/search/title/?{param}{title_type}&sort=user_rating,desc")

        # Create combined genre search
        combined_params = '&'.join([genre_params[g] for g in genres if g in genre_params])
        if combined_params:
            urls.append(f"{self.base_url}/search/title/?{combined_params}{title_type}&sort=user_rating,desc")

        return urls

    def _scrape_search_page(self, url):
        """Scrape a single IMDb search results page"""
        results = []
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all movie items
            items = soup.select('.ipc-metadata-list-summary-item')

            for item in items[:10]:  # Limit to first 10 results per page
                try:
                    title_elem = item.select_one('.ipc-title__text')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = item.select_one('a.ipc-title-link-wrapper')['href']
                    full_link = f"{self.base_url}{link.split('?')[0]}"

                    # Extract year
                    year_elem = item.select_one('.dli-title-metadata-item')
                    year = year_elem.get_text(strip=True) if year_elem else "N/A"

                    # Extract rating
                    rating_elem = item.select_one('.ipc-rating-star')
                    rating = rating_elem.get_text(strip=True).split()[0] if rating_elem else "N/A"

                    # Get synopsis
                    synopsis = self._get_synopsis(full_link)

                    results.append({
                        'title': title,
                        'year': year,
                        'rating': rating,
                        'synopsis': synopsis,
                        'link': full_link
                    })

                except Exception as e:
                    print(f"⚠️ Error processing item: {str(e)}")
                    continue

        except Exception as e:
            print(f"⚠️ Error scraping {url}: {str(e)}")

        return results

    def _get_synopsis(self, url):
        """Get movie synopsis from its detail page"""
        try:
            response = self.session.get(url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Try multiple selectors for synopsis
            synopsis_selectors = [
                '.ipc-html-content-inner-div',
                '.plot_summary .summary_text',
                '.canwrap .plotxl'
            ]

            for selector in synopsis_selectors:
                synopsis_elem = soup.select_one(selector)
                if synopsis_elem:
                    synopsis = synopsis_elem.get_text(strip=True)
                    # Clean up common synopsis text
                    synopsis = re.sub(r'Written by.*$', '', synopsis)
                    synopsis = re.sub(r'—.*$', '', synopsis)
                    return synopsis[:200] + "..." if len(synopsis) > 200 else synopsis

            return "Synopsis not available"
        except:
            return "Synopsis not available"

    def display_recommendations(self, recommendations):
        """Display formatted recommendations"""
        if not recommendations:
            print("⚠️ No matches found. Try different genres.")
            return

        print(f"\n🎉 Here are your personalized recommendations: 🎉")

        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec['title']} ({rec['year']})")
            print(f"   {self.emoji_map['star']} IMDb Rating: {rec['rating']}/10")
            print(f"   {self.emoji_map['star']} Synopsis: {rec['synopsis']}")
            print(f"   {self.emoji_map['star']} Link: {rec['link']}")

    def run(self):
        """Main recommendation workflow"""
        while True:
            # Get user preferences
            genres, content_type = self.get_user_preferences()

            # Search and display recommendations
            recommendations = self.search_imdb(genres, content_type)
            self.display_recommendations(recommendations)

            # Ask if user wants to search again
            choice = input(f"\n{self.emoji_map['popcorn']} Would you like to search again? (yes/no): ").lower()
            if choice not in ['yes', 'y']:
                print(f"\n{self.emoji_map['clapper']} Enjoy your viewing! {self.emoji_map['popcorn']}")
                break

if __name__ == "__main__":
    recommender = ContentRecommender()
    recommender.run()