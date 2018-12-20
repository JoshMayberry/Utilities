import c_Container

print(c_Container.is_container)

x0, y0, x1, y1 = 1, 2, 3, 4
rect_obj = c_Container.PyContainer(x0, y0, x1, y1)
print(rect_obj)
print(rect_obj.get_area)