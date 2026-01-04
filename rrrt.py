import requests
import time

for i in range(2000):

    response = requests.get(r"http://bookmark.test/api/v1/bookmarks/bookmarks?page=1&page_size=50&sort_by=created_time&sort_order=desc", 
                headers={"x-tenant-id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"})

    response.raise_for_status()
    print(i,flush=True)
    time.sleep(0.25)

