# Where the provider-detection keywords come from

`scan.py` names the network behind a domain from three signals, checked in order:
the response headers, the DNS CNAME, then the network announcing the IP address.
This file is the source for the keywords in those tables.

## Headers and CNAMEs

A header or a CNAME suffix is the vendor identifying itself, so each of these has
a page on the vendor's own site behind it.

| Provider | What we look for | Documented at |
| :-- | :-- | :-- |
| Cloudflare | `cf-ray`, `server: cloudflare`, `.cloudflare.net` | [HTTP headers](https://developers.cloudflare.com/fundamentals/reference/http-headers/), [Pages headers](https://developers.cloudflare.com/pages/configuration/serving-pages/), [partial setup](https://developers.cloudflare.com/dns/zone-setups/partial-setup/setup/) |
| Amazon CloudFront | `x-amz-cf-id`, `x-amz-cf-pop`, `via: cloudfront`, `.cloudfront.net` | [response behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorCustomOrigin.html), [alternate domain names](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html) |
| Amazon (AWS origin) | `.elb.amazonaws.com` | [domain names with a load balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/classic/using-domain-names-with-elb.html) |
| Fastly | `x-served-by`, `.fastly.net` | [X-Served-By](https://www.fastly.com/documentation/reference/http/http-headers/X-Served-By), [CNAME records](https://www.fastly.com/documentation/guides/getting-started/domains/working-with-domains/working-with-cname-records-and-your-dns-provider) |
| Akamai | `server: akamai`, `.edgekey.net`, `.edgesuite.net`, `.akamaized.net`, `.akamaiedge.net` | [debug headers](https://techdocs.akamai.com/edgeworkers/docs/standard-debug-header-details), [edge hostnames](https://techdocs.akamai.com/property-mgr/reference/modify-property-hostnames) |
| Azure Front Door | `x-azure-ref`, `x-msedge-ref`, `.azurefd.net` | [Front Door headers](https://learn.microsoft.com/en-us/azure/frontdoor/front-door-http-headers-protocol), [custom domains](https://learn.microsoft.com/en-us/azure/frontdoor/standard-premium/how-to-add-custom-domain) |
| Azure CDN | `.azureedge.net` | [map content to a custom domain](https://learn.microsoft.com/en-us/azure/cdn/cdn-map-content-to-custom-domain) |
| Microsoft (Azure) | `.trafficmanager.net`, `.azurewebsites.net`, `.cloudapp.net` | [Traffic Manager](https://learn.microsoft.com/en-us/azure/traffic-manager/traffic-manager-point-internet-domain), [Microsoft's list of its own service suffixes](https://learn.microsoft.com/en-us/azure/security/fundamentals/subdomain-takeover) |
| Sucuri | `x-sucuri-id` | [cache headers](https://kb.sucuri.net/firewall/Troubleshooting/investigating-cache-headers) |
| BunnyCDN | `.b-cdn.net` | [custom hostname](https://support.bunny.net/hc/en-us/articles/207790279-How-to-set-up-a-custom-CDN-hostname) |
| CDN77 | `.cdn77.org` | [getting started](https://client.cdn77.com/support/knowledgebase/introduction-cdn/getting-started) |
| Gcore | `.gcdn.co` | [custom domain](https://docs.gcore.com/cdn/cdn-resource-options/general/create-and-set-a-custom-domain-for-the-content-delivery-via-cdn) |

A few keywords in the code are not listed above: `x-akamai-transformed`,
`x-iinfo`, `.incapdns.net`, `.edgio.net`, `.llnwd.net`, `.sucuri.net`,
`.cloudflare.com`, `.fastlylb.net` and `.akamai.net`. They are in real use and
they work, but I could not find a page on the vendor's own site where the string
appears, so they are marked here rather than cited to a blog post. Edgio's
documentation went offline when the company wound down.

## Announcing network

The third table is a different kind of thing and there is nothing to cite per
entry, because those keywords are not vendor claims about their products. They
are substrings of names in a routing registry.

The one source that matters is the service the names come from:

- [Team Cymru IP-to-ASN Mapping Service](https://www.team-cymru.com/ip-asn-mapping)
  — free, built from BGP data across 50+ peers and refreshed every four hours,
  queryable over whois at `whois.cymru.com`, which is how `scan.py` asks.

Because it is registration data it says who owns the address block, not who
served the request, which is why this signal is checked last and why a match on
an organisation's own network is recorded as self-hosted rather than as a CDN.

## Standards

What is being measured, as opposed to how the network is named:

- [NIST FIPS 203](https://csrc.nist.gov/pubs/fips/203/final) — ML-KEM, the key
  encapsulation mechanism.
- [draft-ietf-tls-ecdhe-mlkem](https://datatracker.ietf.org/doc/draft-ietf-tls-ecdhe-mlkem/)
  — X25519MLKEM768, the hybrid TLS 1.3 group combining X25519 with ML-KEM-768.
