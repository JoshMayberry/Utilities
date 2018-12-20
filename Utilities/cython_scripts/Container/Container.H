#ifndef Container_H
#define Container_H

namespace shapes {
    class Container {
        public:
            int x0, y0, x1, y1;
            Container();
            Container(int x0, int y0, int x1, int y1);
            ~Container();
            int getArea();
            void getSize(int* width, int* height);
            void move(int dx, int dy);
    };
}

#endif