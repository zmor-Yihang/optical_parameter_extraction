#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据输入输出模块
"""

import os
import pandas as pd

from utils import info, error, exception
from .exceptions import DataReadError, SaveError


def read_data_file(file_path, start_row=1):
    """
    通用数据读取函数，支持Excel和txt文件
    
    参数:
        file_path: 文件路径
        start_row: 数据内容起始行（从1开始，跳过前start_row-1行，无表头）
        
    返回:
        pandas.DataFrame: 包含时间列和强度列的数据框
        
    注意:
        - Excel文件：支持.xlsx和.xls格式
        - txt文件：自动检测分隔符（支持空格、制表符、逗号等分隔符）
    """
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        skip = max(0, int(start_row) - 1)
        
        if file_ext in ['.xlsx', '.xls']:
            # 读取Excel文件
            data = pd.read_excel(file_path, skiprows=skip, header=None, names=['time', 'intensity'], engine='openpyxl')
        elif file_ext == '.txt':
            # 读取txt文件（自动检测分隔符：空格、制表符等）
            try:
                # 先尝试自动检测分隔符
                data = pd.read_csv(file_path, sep=None, skiprows=skip, header=None, names=['time', 'intensity'], engine='python')
            except Exception:
                # 如果自动检测失败，尝试空格分隔
                try:
                    data = pd.read_csv(file_path, sep=' ', skiprows=skip, header=None, names=['time', 'intensity'])
                except Exception:
                    # 最后尝试制表符分隔
                    data = pd.read_csv(file_path, sep='\t', skiprows=skip, header=None, names=['time', 'intensity'])
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")
        
        # 确保数据至少有两列
        if len(data.columns) < 2:
            raise DataReadError(file_path, "数据文件必须至少包含两列：时间和强度")
        
        info(f"成功读取文件: {file_path}")
        # 返回前两列（时间和强度）
        return data.iloc[:, :2]
        
    except DataReadError:
        raise
    except Exception as e:
        exception(f"读取文件 {file_path} 时出错")
        raise DataReadError(file_path, str(e))


def save_results_to_excel(results_data, filename):
    """
    将计算结果保存到Excel文件
    
    参数:
        results_data: 计算结果数据字典
        filename: 保存的文件路径
        
    返回:
        bool: 是否保存成功
        
    Raises:
        SaveError: 保存失败时抛出
    """
    try:
        info(f"开始保存结果到: {filename}")
        
        # 创建一个ExcelWriter对象
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # 获取数据
            F = results_data['F']
            sam_names = results_data['sam_names']
            
            # 创建一个包含频率的DataFrame
            data_dict = {'频率 (THz)': F}
            
            # 为每个样品添加折射率、消光系数、吸收系数、介电常数和介电损耗列
            for i, name in enumerate(sam_names):
                data_dict[f'{name} 折射率'] = results_data['Nsam'][i]
                data_dict[f'{name} 消光系数'] = results_data['Ksam'][i]
                data_dict[f'{name} 吸收系数 (cm^-1)'] = results_data['Asam'][i]
                data_dict[f'{name} 介电常数实部'] = results_data['Epsilon_real'][i]
                data_dict[f'{name} 介电常数虚部'] = results_data['Epsilon_imag'][i]
                data_dict[f'{name} 介电损耗'] = results_data['TanDelta'][i]
            
            # 创建DataFrame并保存到Excel的单个工作表中
            df = pd.DataFrame(data_dict)
            df.to_excel(writer, sheet_name='光学参数', index=False)
        
        info(f"结果已成功保存到: {filename}")
        return True
    except Exception as e:
        exception(f"保存结果到Excel时出错: {str(e)}")
        raise SaveError(filename, str(e))
