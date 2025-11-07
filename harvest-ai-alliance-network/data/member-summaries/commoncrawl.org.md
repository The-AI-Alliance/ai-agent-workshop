## Common Crawl Foundation — Organization Summary

Common Crawl is a 501(c)(3) non-profit (founded in 2007) that builds and maintains a free, open repository of web crawl data for anyone to access and analyze. Its mission is to make wholesale extraction, transformation, and analysis of open web data accessible to researchers and the broader community.

What they provide
- Open web corpus at web scale: over 300 billion pages spanning 15+ years, with 3–5 billion new pages added monthly; cited in 10,000+ research papers.
- Free access via AWS Open Data: dataset hosted in s3://commoncrawl (us-east-1) and over HTTPS at https://data.commoncrawl.org/, with CloudFront access.
- Data formats and artifacts:
  - WARC (raw crawl), WAT (computed metadata), WET (extracted plaintext).
  - URL index for query and retrieval: https://index.commoncrawl.org/.
  - Web graphs (host/domain-level) published regularly.
- Getting started resources: examples, tutorials/use cases, crawl statistics, and infrastructure status page.

Target users and use cases
- Researchers, companies, and individuals in fields such as NLP/ML, information retrieval, digital humanities, social science, economics, and public-sector analysis.
- Common tasks include language modeling, trend analysis, link analysis, content classification, and large-scale text mining.

Technology and operations
- Crawling with CCBot (Nutch/Hadoop/MapReduce pipeline), adaptive politeness (robots.txt, crawl-delay, HTTP 429/5xx backoff), support for sitemaps, conditional GET, gzip/Brotli, and nofollow.
- Access patterns supported via AWS CLI (including anonymous --no-sign-request), HTTP(S) download agents, and big data frameworks (EMR, Spark, Hadoop/S3A).
- Data governance and terms: permissive open data ethos with Terms of Use (updated Mar 7, 2024) emphasizing lawful use and respect for third-party rights; legal opt-out registry published.

Partnerships, ecosystem, and notable updates
- Hosted under AWS Open Data Sponsorships.
- Data included in the Internet Archive’s Wayback Machine.
- 2025 updates: GneissWeb quality/category annotations added (from IBM research), ongoing monthly crawl archives and web graph releases, events and seminars (e.g., Stanford HAI), transparency posts and opt-out registry.
- Mailing address (copyright/DMCA notices): 9663 Santa Monica Blvd., #425, Beverly Hills, CA 90210, USA.

Distinctive aspects
- Uniquely large, openly accessible, regularly updated web corpus (free to access and download).
- Standardized archival formats (WARC/WAT/WET) enabling reproducible, at-scale research.
- Extensive academic impact (10k+ citations) and sustained corpus growth over 15+ years.

Most relevant data points to retain
- Organization: Common Crawl Foundation; 501(c)(3); founded 2007.
- Mission: open, at-scale access to web data for research and analysis.
- Scale metrics: 300B+ pages; 3–5B new pages/month; 10k+ research paper citations.
- Access: s3://commoncrawl (us-east-1); https://data.commoncrawl.org/; CloudFront; URL index https://index.commoncrawl.org/.
- Formats: WARC (raw), WAT (metadata), WET (plaintext).
- Tools/resources: examples, use cases, crawl statistics, infra status.
- Crawler: CCBot (Nutch/Hadoop); respects robots.txt & crawl-delay; supports sitemaps; adaptive throttling.
- Governance: Terms of Use (2024-03-07); opt-out registry; emphasis on lawful, respectful use.
- Ecosystem: AWS Open Data program; inclusion in Internet Archive Wayback Machine; 2025 GneissWeb annotations integration; ongoing web graphs and monthly crawl releases.
- Contact/mailing (DMCA): 9663 Santa Monica Blvd., #425, Beverly Hills, CA 90210, USA.
