"""CLI 入口：python -m lifelens"""
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="lifelens",
        description="LifeLens 旅游数据爬取与分析系统",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    subparsers.add_parser("ctrip-list", help="获取携程景点列表")
    subparsers.add_parser("ctrip-detail", help="获取携程景点详情")
    subparsers.add_parser("ctrip-comments", help="爬取携程景点评论")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    print(f"命令 {args.command} 尚未接入，请直接使用各模块的 __main__ 进行测试")


if __name__ == "__main__":
    main()
