"""
添加示例爬虫项目数据
"""
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import Project, Spider, SpiderType, SpiderStatus
from datetime import datetime


def add_sample_data(db: Session):
    """添加示例数据"""
    
    print("=" * 60)
    print("  添加示例爬虫项目数据")
    print("=" * 60)
    
    # 1. 创建示例项目：电商数据采集
    print("\n[1/3] 创建示例项目...")
    ecommerce_project = Project(
        name="电商数据采集",
        team_id=1,
        description="采集主流电商平台的商品数据，包括淘宝、京东、拼多多等",
        status="active"
    )
    db.add(ecommerce_project)
    db.commit()
    db.refresh(ecommerce_project)
    print(f"  ✓ 创建项目: {ecommerce_project.name} (ID: {ecommerce_project.id})")
    
    # 2. 创建示例爬虫1： Crawlo电商爬虫
    print("\n[2/3] 创建示例爬虫...")
    crawlo_ecommerce_spider = Spider(
        name="Crawlo电商爬虫",
        project_id=ecommerce_project.id,
        description="使用 Crawlo 框架采集电商平台商品数据，支持分布式爬取和智能反反爬",
        spider_type='crawlo',
        status=SpiderStatus.ACTIVE,
        entry_file="main.py",
        git_url="https://github.com/example/crawlo-ecommerce.git",
        git_branch="main",
        run_count=256,
        success_count=248,
        error_count=8
    )
    db.add(crawlo_ecommerce_spider)
    db.commit()
    db.refresh(crawlo_ecommerce_spider)
    print(f"  ✓ 创建爬虫: {crawlo_ecommerce_spider.name} (ID: {crawlo_ecommerce_spider.id})")
    
    # 3. 创建示例爬虫2： Crawlo社交媒体爬虫
    crawlo_social_spider = Spider(
        name="Crawlo社交媒体爬虫",
        project_id=ecommerce_project.id,
        description="基于 Crawlo 框架采集社交媒体平台的商品推广和评价数据",
        spider_type='crawlo',
        status=SpiderStatus.ACTIVE,
        entry_file="spiders/social_media.py",
        git_url="https://github.com/example/crawlo-social.git",
        git_branch="main",
        run_count=189,
        success_count=185,
        error_count=4
    )
    db.add(crawlo_social_spider)
    db.commit()
    db.refresh(crawlo_social_spider)
    print(f"  ✓ 创建爬虫: {crawlo_social_spider.name} (ID: {crawlo_social_spider.id})")
    
    # 4. 创建示例爬虫3：Scrapy爬虫(次要)
    scrapy_spider = Spider(
        name="商品比价爬虫(Scrapy)",
        project_id=ecommerce_project.id,
        description="使用 Scrapy 框架进行多平台商品价格对比采集",
        spider_type='scrapy',
        status=SpiderStatus.DRAFT,
        entry_file="spiders/price_compare.py",
        git_url="https://github.com/example/scrapy-price.git",
        git_branch="master"
    )
    db.add(scrapy_spider)
    db.commit()
    db.refresh(scrapy_spider)
    print(f"  ✓ 创建爬虫: {scrapy_spider.name} (ID: {scrapy_spider.id})")
    
    # 5. 创建第二个示例项目：新闻资讯采集
    print("\n[3/3] 创建第二个示例项目...")
    news_project = Project(
        name="新闻资讯采集",
        team_id=1,
        description="采集主流新闻网站的最新资讯内容",
        status="active"
    )
    db.add(news_project)
    db.commit()
    db.refresh(news_project)
    print(f"  ✓ 创建项目: {news_project.name} (ID: {news_project.id})")
    
    # 新闻爬虫1：Crawlo框架
    crawlo_news_spider = Spider(
        name="Crawlo新闻爬虫",
        project_id=news_project.id,
        description="使用 Crawlo 框架采集主流新闻网站资讯，支持智能去重和增量更新",
        spider_type='crawlo',
        status=SpiderStatus.ACTIVE,
        entry_file="main.py",
        git_url="https://github.com/example/crawlo-news.git",
        git_branch="main",
        run_count=542,
        success_count=538,
        error_count=4
    )
    db.add(crawlo_news_spider)
    db.commit()
    db.refresh(crawlo_news_spider)
    print(f"  ✓ 创建爬虫: {crawlo_news_spider.name} (ID: {crawlo_news_spider.id})")
    
    # 新闻爬虫2：Playwright(用于动态渲染页面)
    playwright_news_spider = Spider(
        name="动态新闻爬虫(Playwright)",
        project_id=news_project.id,
        description="使用 Playwright 处理JavaScript渲染的新闻页面和滚动加载内容",
        spider_type='playwright',
        status=SpiderStatus.ACTIVE,
        entry_file="spiders/dynamic_news.py",
        git_url="https://github.com/example/playwright-news.git",
        git_branch="main",
        run_count=128,
        success_count=125,
        error_count=3
    )
    db.add(playwright_news_spider)
    db.commit()
    db.refresh(playwright_news_spider)
    print(f"  ✓ 创建爬虫: {playwright_news_spider.name} (ID: {playwright_news_spider.id})")
    
    print("\n" + "=" * 60)
    print("  ✓ 示例数据添加完成！")
    print("=" * 60)
    print("\n示例数据概览：")
    print(f"  - 项目数量: 2")
    print(f"  - 爬虫数量: 5")
    print(f"  - 项目1: 电商数据采集 (3个爬虫)")
    print(f"    • Crawlo电商爬虫 (Crawlo框架, 运行256次) [主打]")
    print(f"    • Crawlo社交媒体爬虫 (Crawlo框架, 运行189次) [主打]")
    print(f"    • 商品比价爬虫 (Scrapy, 草稿) [次要]")
    print(f"  - 项目2: 新闻资讯采集 (2个爬虫)")
    print(f"    • Crawlo新闻爬虫 (Crawlo框架, 运行542次) [主打]")
    print(f"    • 动态新闻爬虫 (Playwright, 运行128次)")
    print("=" * 60)


def main():
    """主函数"""
    db = SessionLocal()
    try:
        add_sample_data(db)
    except Exception as e:
        print(f"\n✗ 添加示例数据失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
