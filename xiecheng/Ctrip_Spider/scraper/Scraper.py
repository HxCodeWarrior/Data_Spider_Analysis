class Scraper:
    def __init__(self, crawl_logger):
        self.logger = crawl_logger

    def start_scraping(self, urls, spot_name, comment_types, comments_per_page):
        last_info = self.logger.last_successful_scrape()
        last_url, last_spot_name, last_comment_type, last_page, last_comment_count = last_info

        for url_item in urls:
            if self._should_resume(url_item, last_url, spot_name, last_spot_name):
                comment_types = self.resume_from_last_type(last_comment_type, comment_types)
                self.scrape_url(url_item, spot_name, comment_types, last_page, last_comment_count)
            else:
                self.scrape_url(url_item, spot_name, comment_types)

    def _should_resume(self, current_url, last_url, current_spot_name, last_spot_name):
        """判断是否应该从上次中断的地方继续爬取"""
        return current_url == last_url and current_spot_name == last_spot_name

    def scrape_url(self, url, spot_name, comment_types, start_page=1, start_comment_count=0):
        """爬取指定URL的评论"""
        for comment_type in comment_types:
            page = start_page
            while True:
                try:
                    comments = self.fetch_comments(comment_type, page)
                    if not comments:
                        break
                    self._process_comments(comments, url, spot_name, comment_type, page, start_comment_count)
                    page += 1
                except Exception as e:
                    self.logger.log_error(url, spot_name, e)
                    return

    def _process_comments(self, comments, url, spot_name, comment_type, page, start_comment_count=0):
        """处理评论数据"""
        comment_count = len(comments)
        if page == 1 and start_comment_count:
            comments = comments[start_comment_count:]
            comment_count = len(comments)
        self.logger.log_scrape_info(url, spot_name, comment_type, page, comment_count)

    @staticmethod
    def resume_from_last_type(last_comment_type, comment_types):
        """从上次的评论类型恢复，跳过已经爬取过的评论类型"""
        if last_comment_type in comment_types:
            index = comment_types.index(last_comment_type)
            return comment_types[index + 1:]
        return comment_types

    @staticmethod
    def fetch_comments(comment_type, page):
        """模拟爬取评论数据"""
        return [f"Comment {index} on page {page} for {comment_type}" for index in range(5)]