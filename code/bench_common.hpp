#pragma once
#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include <chrono>
#include <stdexcept>
#include <nvtx3/nvToolsExt.h>
using Pair=std::pair<std::string,std::string>;
inline std::vector<Pair> load(const char* file){
    std::ifstream in(file);if(!in)throw std::runtime_error("input open");
    std::vector<Pair> r;std::string a,b;
    while(std::getline(in,a)){
        if(!std::getline(in,b)||a[0]!='>'||b[0]!='<')throw std::runtime_error("input format");
        r.push_back({a.substr(1),b.substr(1)});
    }if(r.empty())throw std::runtime_error("empty input");return r;
}
inline double now_ms(){return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();}
inline void write_scores(const char* file,const std::vector<int>& scores){std::ofstream f(file);for(int s:scores)f<<s<<'\n';}
