# 构象生成
1. 从.smi文件夹中使用rdkit生成构象
python ../generate_conformers.py * --output_dir * --workers * --verbose
*: .smi文件， 每一行是一个smiles，或者smiles  name
--output_dir: 输出文件夹
--workers: CPU并行核数

2. 使用omol进行进一步优化
python ../multi_gpu_omol_optimize.py * --gpu_ids * --verbose
*: 上一步的输出文件夹
*: 使用的gpu，格式为0,1,2 或者 0*4, 1*4, 其中4为该GPU上的任务数

# 初筛
3. 准备ORCA .inp文件
python orca_file_prepare.py -d * -t omol_opt -o * -f template/orca_s1t1.inp
-d: 上一步的输出文件夹
-o: 输出文件夹

4. 提交（可选）
python submit_orca_batch.py * * --cores-per-task 4
* *: 前面的输出文件夹， 总的cpu核数

5. 打包（可选）,转移至其余计算资源上进行计算
5.1 将步骤2的输出文件夹压缩为tar.gz
tar -czvf *.tar.gz *
5.2 清除步骤3创建的文件夹 

# 进一步筛选
6. 从OMol结构计算的S1T1结果中，筛选需要进一步计算的分子
python extract_molecules.py -i * -d * -o * 
-i: 输入csv文件，包含moleucle, Energy_Difference_eV 
-d: 原始OMol opt 文件夹
-o: 输出文件夹

7. 生成ORCA .inp文件， 
7.1 T1 OPT 输入文件
python orca_file_prepare.py -d * -t omol_opt -o * -f template/step1_orca_t1_opt.inp --inp_name t1_opt --additional_multiplicity 2
-d: 上一步的输出文件夹
-o: 输出文件夹

7.2 SOC 输入文件
python orca_file_prepare.py -d * -t omol_opt -o * -f template/step2_orca_soc.inp --inp_name soc_cal --xyz_name t1_opt
-d: 6.输出文件夹
-o: 7.1输出文件夹

8. 提交（可选）
8.1 提交T1 opt
python submit_orca_batch.py * * --cores-per-task 4 --inp-name t1_opt
* *: 前面的输出文件夹， 总的cpu核数
8.2 提交SOC 
python submit_orca_batch.py * * --cores-per-task 4 --inp-name soc_cal

9. 打包（可选）
9.1 将步骤2的输出文件夹压缩为tar.gz
tar -czvf *.tar.gz *
9.2 清除步骤1， 步骤2创建的文件夹 
